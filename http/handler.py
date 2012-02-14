#
# Copyright 2012 ASAF
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from tornado import web
from tornado import database

import os
import re
import functools
import hashlib
import shutil
import mimetypes
from datetime import datetime
from urlparse import urlsplit
from lxml import etree
import urllib

from ifheader import if_header_evaluate
from index import collection_index
from dav.davelement import *
from dav.properties import DbAdapter, PropFindParser, PropPatchParser
from dav.lock import Lockdb, LockDiscovery, LockParser, parse_timeout


"""RFC4918 implemeantation  
   Http request handler for Web Distributed Authoring and Versioning, 
   Based on the Tornado framework.
"""

DAV_VERSION = "1,2"
INTERNAL_SERVER_ERROR = 500

Unauthorized = """\
<html><head><title>401: Unauthorized</title></head><body>
401: Unauthorized
</body></html>"""

Forbidden = """\
<html><head><title>403: Forbidden</title></head><body>
403: Forbidden
</body></html>"""

MovedPermanatly = """\
<html><head><title>301: Moved Permanatly </title></head><body>
The resource has moved: %s
</body></html>"""

InternalError = """\
<html><head><title>500: Internal server error</title></head><body>
Server Error %s
</body></html>"""


def authenticated(method):
    """Decorate methods with this to require that the user be logged in."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if  self.application.auth!=None and not self.current_user:
            authorization = self.request.headers.get("authorization")
            if not authorization:
                    """send 401 error with WWW-Authenticate header"""
                    self.set_header('WWW-Authenticate', self.application.auth.get_header())
                    self.set_status(401)
                    self.write(Unauthorized)
                    self.finish()
                    return
            else:
                auth_type, auth_param =  authorization.split (' ', 1)                      
                if not self.application.auth.authenticate( self.request, auth_param ):
                    """send 403 error"""
                    self.set_status(403)
                    self.write(Forbidden)
                    self.finish()
                    return
            self._current_user =  self.application.auth.username    
        return method(self, *args, **kwargs)
    return wrapper


class BasicHandler(web.RequestHandler):
    """Basic method handler for http request
    """

    def initialize(self):
        pass
                                
    def server_error(self,error):
        self.set_status(INTERNAL_SERVER_ERROR)
        self.finish(InternalError%error)
        
    def moved_permanatly(self):
        self.set_header('Location', self.request.uri+"/")
        self.set_status(301)
        self.write(MovedPermanatly % (self.request.uri+"/"))
        self.finish()

    def get(self):
        self.finish("""\
        <html>
            <head>
                <title>Welcome</title>
            </head>
            <body>
                <h1>Welcome to my WebDav server</h1>
            </body>
            </html>
        """)
        
    def post(self):
        self.get()

    def head(self):
        self.set_header('Allow',  
            ",".join (["GET", "HEAD", "OPTIONS"]) )
        self.finish()
        
    def options(self):
        self.set_header('Allow',  
            ",".join (["GET", "HEAD", "OPTIONS"]) )
        self.finish()


class RootHandler(BasicHandler):
    """ Handle basic root object requests, i.e just redirect 
        for exisiting directory or serve get request for files
    """

    SUPPORTED_METHODS = ("HEAD", "GET", "POST", "OPTIONS", 
            "PUT", "DELETE", "MKCOL", 
            "PROPFIND", "PROPPATCH", 
            "MOVE", "COPY", "LOCK", "UNLOCK")
    
    def options(self, name):
        self.set_header('Allow',  
            ",".join (["HEAD", "GET", "OPTIONS"]) )
        filename = os.path.abspath(os.path.join(self.application.directory, name)) 
        if not os.path.exists(filename):
            raise web.HTTPError(404) 
        elif os.path.isdir(filename):
            self.moved_permanatly()
            return                                            
        self.finish()

    def get(self, name, with_body=True):
        """Serve regular file for root directory no DAV properties
        """
        filename = os.path.abspath(os.path.join(self.application.directory, name)) 
        if not os.path.exists(filename):
            raise web.HTTPError(404) 
        elif os.path.isdir(filename):
            self.moved_permanatly()
            return                                            
        elif with_body:
            try:
                object_file = open(filename, "r")
                try:
                    self.finish( object_file.read() )
                finally:
                    object_file.close()
            except (IOError, os.error), why:
                raise web.HTTPError(500) 
        else:
            self.finish()
                
    def post(self, name):
        self.get(name)

    def head(self, name):
        self.set_header('Allow',  
            ",".join (["HEAD", "GET", "OPTIONS"]) )
        self.get(name, with_body=False)    
        
    def put(self, name):
        raise web.HTTPError(405)  

    def mkcol(self, name):
        raise web.HTTPError(405)  

    def move(self, name):
        raise web.HTTPError(405)  

    def copy(self, name):
        raise web.HTTPError(405)  

    def delete(self, name):
        raise web.HTTPError(405)  

    def propfind(self, name):
        """ This is because some clients insists on calling PROPFIND
            On the root file
        """
        filename = os.path.abspath(os.path.join(self.application.directory, name)) 
        if os.path.isdir(filename):
            self.moved_permanatly()
        else:
            raise web.HTTPError(405) 

    def proppatch(self, name):
        raise web.HTTPError(405)  

    def lock(self, name):
        raise web.HTTPError(405)  

    def unlock(self, name):
        raise web.HTTPError(405)  


class ObjectHandler(RootHandler):
    """ Handle object requests
        methods are delegate to the coresponding object method
    """
    def _object(self, **kw):
        """ object factory method """
        return self.application._object(self.application, **kw)

    def _object_fromuri(self, uri):
        """ object from uri factory method """
        return self.application._object.fromuri_factory( self.application, uri )         
    
    def _if_header_evaluate(self):
        return if_header_evaluate(self.application, self.request) 
        
    def _if_header_match(self, ifh_result, locks):
        if ifh_result=={} or ifh_result==None:
            return None  
        for lock in locks:
            for uri in ifh_result.keys():
                # result can be parent of resource 
                # of unmmaped If list 
                if uri.startswith(lock.resource) and \
                    lock.token in ifh_result[ uri ]:
                    return lock   
        return None
         
    def _is_locked(self, obj, ifh_result):
        """ verify that the object is not locked
        """
        locks  = self.application.lockdb.all_locks(obj.uri)
        if locks == []:
            return              
        if self._if_header_match( ifh_result, locks ):
            return    
        raise web.HTTPError(423)
                
    def _has_dependent_lock(self, obj, ifh_result):
        """ verify that a collection object has no dependent locks
        """
        locks  = self.application.lockdb.dependent_lock(obj.uri)
        if locks == []:
            return   
        if self._if_header_match( ifh_result, locks ):
            return    
        raise web.HTTPError(423)
  
    def options(self, collection, filename=''):
        dav_object = self._object(parent = collection, name = filename)
        if not dav_object.is_exists() or \
            not dav_object.is_collection() and filename == '':
            raise web.HTTPError(404) 
        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 
        self.set_header('Allow',  
            ",".join ( method for method in self.SUPPORTED_METHODS) )
        self.set_header('Dav', DAV_VERSION)
        self.finish()
                                    
    @authenticated      
    def mkcol(self, collection, filename=''):
        """Handle collection create request
        """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 

        if self.request.body!='':
            raise web.HTTPError(415) 

        if filename!='' or self.request.uri[-1]!='/':
            self.moved_permanatly()
            return    

        dav_object = self._object(parent = collection, name = filename)
        if dav_object.is_exists():
            raise web.HTTPError(405)           

        self._is_locked( dav_object, ife )  
        rc = dav_object.mkcol()
        if rc/100!=2:
            raise web.HTTPError(rc)                                       

        self.set_status(rc)           
        self.finish()

    @authenticated      
    def put(self, collection, filename=''):
        """ Put a new object """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 
        
        parent_object = self._object(parent = collection)
        if not parent_object.is_exists():
            raise web.HTTPError(409)   
        
        dav_object = self._object(parent = collection, name = filename)
        self._is_locked( dav_object, ife ) 
        content_length = self.request.headers.get('content-length') 
        if content_length:
            try:
                length = int (content_length)
            except:
                raise web.HTTPError(400)
            if self.application.max_upload > 0 and \
                int(content_length) > self.application.max_upload:
                raise web.HTTPError(400)
        else:
            if self.application.max_upload > 0 and \
                len( self.request.body ) > self.application.max_upload:
                raise web.HTTPError(400)
            
        dav_object.write(self.request.body)                     
        self.set_status(201)           
        self.finish()

    @authenticated      
    def get(self, collection, filename='', with_body=True):
        """ Return an index of the object if a collection
        """   
        SIZE = 4*1024
        dav_object = self._object(parent = collection, name=filename)
        if not dav_object.is_exists() or \
            not dav_object.is_collection() and filename == '':
            raise web.HTTPError(404) 

        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 

        self.set_header("Last-Modified", dav_object.lastmodifieddate())
        self.set_header("Content-Type", 'text/html')
        self.set_header("Etag", dav_object.etag)
        
        inm = self.request.headers.get("If-None-Match")
        if inm and inm.find(dav_object.etag) != -1:
            self.set_status(304)
        elif with_body:
            if dav_object.is_collection():
                self.write( collection_index( self.request, dav_object ) )
            else:
                try:
                    object_file = open(dav_object.filename, "rb")
                    try:
                        buf = object_file.read(SIZE)
                        while buf!='':
                            self.write( buf )
                            self.flush()
                            buf = object_file.read(SIZE)
                    finally:
                        object_file.close()
                except (IOError, os.error), why:
                    pass

        self.finish()

    @authenticated
    def post(self, collection, filename=''):
        self.get( collection, filename )

    @authenticated
    def head(self, collection, filename=''):
        self.set_header('Allow',  
            ",".join (method for method in self.SUPPORTED_METHODS) )
        self.set_header('Dav', DAV_VERSION)
        self.get( collection, filename, with_body=False )

    @authenticated
    def copy(self, collection, filename='', move=False):
        """ Copy / Move method
        """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 

        dav_object = self._object(parent = collection, name = filename)
        if not dav_object.is_exists() or \
            not dav_object.is_collection() and filename == '':
            raise web.HTTPError(404) 

        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 

        overwrite_header = self.request.headers.get('overwrite') 
        destination = self.request.headers.get('destination')  
        if destination==None:
            raise web.HTTPError(400)

        urld = urlsplit (destination)
        if urld.path=='':
            raise web.HTTPError(400) 

        # cannot copy on itself
        if re.match(urld.path, self.request.uri)!=None:
            raise web.HTTPError(409)

        if move:
            # check locks on source if move
            self._is_locked( dav_object, ife )                          
            self._has_dependent_lock ( dav_object, ife )

        d = self._object_fromuri(urld.path)
        self._is_locked( d, ife )                          
        self._has_dependent_lock ( d, ife )

        if move:
            rc = dav_object.move( d.filename,  overwrite_header )
        else:
            rc = dav_object.copy( d.filename,  overwrite_header )

        if rc/100!=2:
            raise web.HTTPError(rc)                                       

        adapter = DbAdapter(self.application.db)
        if move:
            if dav_object.is_collection():
                adapter.move_collection( self.request.uri, urld.path )
            else:
                adapter.move_properties( self.request.uri, urld.path )
        else:
            if dav_object.is_collection():
                adapter.copy_collection( self.request.uri, urld.path )
            else:
                adapter.copy_properties( self.request.uri, urld.path )

        self.set_status(rc)           
        self.finish()

    @authenticated
    def move(self, collection, filename=''):
        """ Move 
        """
        self.copy( collection, filename, move = True )        
        
    @authenticated
    def delete(self, collection, filename=''):
        """ Delete 
        """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 

        dav_object = self._object(parent = collection, name = filename)
        if not dav_object.is_exists() or \
            not dav_object.is_collection() and filename == '':
            raise web.HTTPError(404) 

        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 

        self._is_locked( dav_object, ife )                          
        self._has_dependent_lock ( dav_object, ife )

        rc = dav_object.delete()
        if rc/100!=2:
            raise web.HTTPError(rc)                                       
        
        adapter = DbAdapter(self.application.db)
        if dav_object.is_collection():
            adapter.delete_collection(self.request.uri)
        else:
            adapter.delete_properties(self.request.uri)

        self.set_status(rc)           
        self.finish()

    @authenticated      
    def propfind(self, collection, filename=''):
        """ Propfind 
        """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 

        dav_object = self._object(parent = collection, name = filename)
        if not dav_object.is_exists() or \
            not dav_object.is_collection() and filename == '':
            raise web.HTTPError(404) 

        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 

        depth = self.request.headers.get('depth')  
        if depth:
            if depth == "infinity":
                depth = None
            else:
                try: 
                    depth = int (depth)
                except:
                    depth = None
            
        if dav_object.is_collection() and depth!=0 and depth!=1:
            raise web.HTTPError(400) 
        
        try:
            parser = PropFindParser(self.request.body)    
        except:
            raise web.HTTPError(400) 

        response = dav_object.propfind( parser, depth )
        if isinstance (response, int):
            raise web.HTTPError(response)

        self.set_header("Content-Type", "text/xml; charset=UTF-8")
        self.set_status(response[0])
        self.write ( etree.tostring(MultistatusElement(*response[1]), 
                        pretty_print=True, 
                        encoding='UTF-8', 
                        xml_declaration=True))                       
        self.finish()       

    @authenticated      
    def proppatch(self, collection, filename=''):
        """ Proppatch 
        """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 

        dav_object = self._object(parent = collection, name = filename)
        if not dav_object.is_exists() or \
            not dav_object.is_collection() and filename == '':
            raise web.HTTPError(404) 

        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 

        self._is_locked( dav_object, ife )

        try:
            parser = PropPatchParser(self.request.body)    
        except:
            raise web.HTTPError(400) 
       
        response = dav_object.proppatch( parser ) 
        if isinstance (response, int):
            raise web.HTTPError(response)

        self.set_header("Content-Type", "text/xml; charset=UTF-8")
        self.set_status(response[0])
        self.write ( etree.tostring(MultistatusElement(*response[1]), 
                        pretty_print=True, 
                        encoding='UTF-8', 
                        xml_declaration=True))                       
        self.finish()       
           
    @authenticated      
    def lock(self, collection, filename=''):
        """ Lock object
        """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 

        dav_object = self._object(parent = collection, name = filename)
        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 

        if not dav_object.is_exists():
            # you can lock non-existing object
            # how wonderfull is that?
            if self.request.body=='':
                raise web.HTTPError(400)  

            parent_object = self._object(parent = collection)                
            if not parent_object.is_exists():
                raise web.HTTPError(409)                 

            # create an empty resource
            dav_object.write()

        depth = self.request.headers.get('depth')  
        if depth == "infinity":
            depth = None
        else:
            try: 
                depth = int (depth)
            except:
                depth = None

        if depth!=0 and depth!=None:
            depth = None

        timeout_header = self.request.headers.get('timeout')  
        if timeout_header:
            timeout = parse_timeout( timeout_header )
        else:
            timeout = None

        if self.request.body == '':
            # Try to refresh locked object
            locks = self.application.lockdb.all_locks( dav_object.uri )
            if locks==[]:
                raise web.HTTPError(400)     
            
            lock = self._if_header_match( ife, locks )
            if lock:      
                # resresh the lock
                self.application.lockdb.refresh_lock(lock.id, timeout) 
                discovery = LockDiscovery( lock.Activelock() )
                lockdiscovery = etree.tostring(PropElement (discovery) , 
                      encoding='UTF-8', 
                      pretty_print=True,
                      xml_declaration=True)
                self.set_header("Content-Type", "text/xml; charset=UTF-8")
                self.set_status(207)
                self.write(lockdiscovery)   
            else:                                           
                raise web.HTTPError(423) 

        else:
            # Try to lock object
            try:
                parser = LockParser(self.request.body)
            except:
                raise web.HTTPError(400) 

            rc = dav_object.lock(parser, timeout, depth)
            if isinstance (rc, int):
                raise web.HTTPError(rc)
        
            status   = rc[0]
            self.set_header("Content-Type", "text/xml; charset=UTF-8")
            self.set_status(status)
            if status == 207:
                lockdiscovery = etree.tostring(PropElement (*rc[1]) , 
                            encoding='UTF-8', 
                            pretty_print=True,
                            xml_declaration=True)
                self.write(lockdiscovery)   

            elif status==200 or status==201:
                token_s = '<' + 'opaquelocktoken:' + rc[1][0] + '>'
                self.set_header("Lock-Token", token_s)

                lockdiscovery = etree.tostring( PropElement(rc[1][1]) , 
                            encoding='UTF-8', 
                            pretty_print=True,
                            xml_declaration=True)
                self.write(lockdiscovery)
            else:
                raise web.HTTPError( 500 )                                           

        self.finish()
           
    @authenticated      
    def unlock(self, collection, filename=''):
        """ Unlock object
        """
        ife = self._if_header_evaluate()
        if ife!=None and ife=={}:
            raise web.HTTPError(412) 

        dav_object = self._object(parent = collection, name = filename)
        if not dav_object.is_exists() or \
            not dav_object.is_collection() and filename == '':
            raise web.HTTPError(404) 

        if dav_object.is_collection() and filename != '':
            self.moved_permanatly()
            return                                 

        lock_token_header = self.request.headers.get('Lock-Token')  
        if lock_token_header:
            lock_match = re.match(r'<opaquelocktoken:([0-9a-f\-]+)>', lock_token_header)
            if lock_match:
                lock_token = lock_match.group(1)
            else:
                raise web.HTTPError(400) 
        else:
            raise web.HTTPError(400) 

        self.set_status( dav_object.unlock(lock_token) )    
        self.finish()

