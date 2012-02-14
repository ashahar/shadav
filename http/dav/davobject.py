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

import calendar
import time
from email.utils import formatdate
from datetime import datetime

from davelement import *
from properties import Properties, DbAdapter
from lock import LockDiscovery, EXCLUSIVE, SHARED

class DavObject(object):
    """ 
        Dav basic object
        represents a file tree like hierarchy of object and its properties
    """
    
    def __init__(self, appliction=None, parent='', name=''):
        self.application = appliction
        if self.application:            
            self.root = appliction.directory
        else:
            self.root = ''
            
        self.parent = parent
        self.name = name               
        self.exists = False
        self.collection = False
        self.st_mtime = 0
        self.st_ctime = 0
        self.st_size = 0
        self.etag = ""

        self._properties = [
            ('{DAV:}creationdate'    , 'creationdate' ),
            ('{DAV:}getcontentlength', 'getcontentlength' ),
            ('{DAV:}getlastmodified' , 'getlastmodified' ), 
            ('{DAV:}resourcetype'    , 'resourcetype' ),
            ('{DAV:}getetag'         , 'getetag' ),
            ('{DAV:}getcontenttype'  , 'getcontenttype' ),
            ]            

    def get_properties(self):
        adapter = DbAdapter(self.application.db)        
        adapter.select(self.uri)
        locks   = self.application.lockdb.all_locks(self.uri)
        return Properties(self, adapter, locks)
        
    def is_collection(self):
        return self.collection

    def is_exists(self):
        return self.exists

    def childs(self):
        """ return a list of childs of this resource
        """
        return []

    def contenttype(self):
        return "application/unknown"

    def lastmodifieddate(self):
        """ return a last modified date in datetime tuple
        """
        return datetime.utcfromtimestamp(
            self.st_mtime)

    def lastmodified(self):
        """ return a last modified date string in ISO format
        """
        t = calendar.timegm(time.gmtime(self.st_mtime))
        return formatdate(t, localtime=True, usegmt=True)

    def getcontenttype(self):
        """ getcontenttype Dav elenment
            The return type must be a XML element or None
        """
        return DAVElement.getcontenttype(self.contenttype())

    def resourcetype(self):
        """ resourcetype Dav elenment
            The return type must be a XML element or None
        """
        if self.collection:
            return DAVElement.resourcetype(CollectionElement)
        return None

    def creationdate(self):
        """ creationdate Dav elenment
            The return type must be a XML element or None
        """
        return DAVElement.creationdate (time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.st_ctime)) )

    def getlastmodified(self):
        """ getlastmodified Dav elenment
            The return type must be a XML element or None
        """
        t = calendar.timegm(time.gmtime(self.st_mtime))
        return DAVElement.getlastmodified(
            formatdate(t, localtime=False, usegmt=True) )

    def getcontentlength(self):
        """ getcontentlength Dav elenment
            The return type must be a XML element or None
        """
        return DAVElement.getcontentlength( str(self.st_size) )

    def getetag(self):
        """ getetag Dav elenment
            The return type must be a XML element or None
        """
        return DAVElement.getetag (self.etag)

    def properties(self):
        return dict (self._properties)

    def propfind(self, parser, depth=0):
        """ Propfind Dav method
        """
        response = []
        props    = self.get_properties()
        prop_e   = props.propfind(parser.prop_list, parser.propname)           
        href_e   = HrefElement(self.uri)
        response.append ( ResponseElement(href_e, *prop_e) )       
        if self.collection and depth==1:
            childs = self.childs()
            for child in childs:
                props    = child.get_properties()
                prop_e   = props.propfind(parser.prop_list, parser.propname)
                href_e   = HrefElement(child.uri)
                response.append ( ResponseElement(href_e, *prop_e) )
                
        return ( 207, response )

    def proppatch(self, parser):       
        """ Proppatch Dav method
        """
        props    = self.get_properties()
        prop_e   = props.proppatch( parser.property_set, parser.property_remove)
        href_e   = HrefElement(self.uri)
        response = ResponseElement(href_e, *prop_e)
        return ( 207, response  )
              
    def lock(self, parser, timeout=None, depth=None):
        """ Lock of a resource 
            If resource is a collection then the lock apply
            to all childrens when depth infinity or the resource
            itself when depth is zero.
        """             
        exclusive = self.application.lockdb.exclusive_lock(self.uri)
        if exclusive!=[]:
            return 423

        # do not allow exlusive locks on resource with shared lock
        shared = self.application.lockdb.shared_lock(self.uri)
        if shared!=[]:
            if parser.lockscope == EXCLUSIVE:
                return 423

        if self.collection and depth==None:
            # do we have a lock on child object of infinite lock on parent?
            if parser.lockscope == EXCLUSIVE:
                conflict = self.application.lockdb.dependent_lock(self.uri)  
            else:
                conflict = self.application.lockdb.conflict_lock(self.uri)  
            
            if conflict!=[]:
                response = []
                response.append (get_response(conflict[0].resource, 403))
                response.append (get_response(self.uri, 424))
                return (207, response)

        lockid = self.application.lockdb.add_lock(self.uri, 
                            parser.lockscope, 
                            depth, 
                            timeout, 
                            parser.owner) 

        lock = self.application.lockdb.getbyid(lockid)
        if lock==None: 
            # something very bad should not continue
            return 500
            
        discovery = LockDiscovery( lock.Activelock() )
        return (200, (lock.token, discovery))
        
    def unlock(self, lock_token):  
        """ Try to release the lock on a resource
        """
        lock = self.application.lockdb.getbytoken(lock_token)
        if lock != None:
            self.application.lockdb.remove_lock( lock.id ) 
        return 204            


