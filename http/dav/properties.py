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

import os
import traceback
import mimetypes
import time
import re
import hashlib
from httplib import responses as http_responses
from lxml import etree
from lxml.etree import _Element
from functools import partial

from davelement import *
from lock import Supportedlock, LockDiscovery, Lockdb
HTTP_OK = 200

""" Dav Propertis 
   
    Handling of object Live and Dead properties, implementing
    propfind and proppatch, dead properties are handled by database
    class adapter allowing for other database to be easily pluged in.
    The current implementation has a mysql adapter only.
"""

qnamere = re.compile(r'^\{(.+)\}(.+)')
def split_qname(qname):
    m = qnamere.match(qname)
    if m:
        return m.groups()
    return None

class PropFindParser():
    """ Prop find request parser
        The spec allows for empty request which should
        return the default properties
    """
    def __init__(self, xdoc):
        self.allprop = False
        self.propname = False
        self.prop_list = None
        if xdoc == '' or xdoc==None:
            return
        root = etree.fromstring(xdoc)                  
        if root.tag!='{DAV:}propfind':
            raise 
        if len(root)>0:
            if root[0].tag == '{DAV:}propname':
                self.propname=True
            elif root[0].tag == '{DAV:}allprop': 
                self.allprop = True
            elif root[0].tag == '{DAV:}prop':
                self.prop_list = [prop.tag for prop in list( root[0] )]
            else:
                raise

class PropPatchParser():
    """ Prop patch request parser
        only porperty set and remove are allowed 
    """
    def __init__(self, xdoc):
        root = etree.fromstring(xdoc)
        self.property_set = None
        self.property_remove = None
        if root.tag!='{DAV:}propertyupdate':
            raise
        for child in root:
            if child.tag == "{DAV:}set":
                prop = child[0]
                if prop.tag == "{DAV:}prop":
                    if self.property_set==None: 
                        self.property_set = list(prop)
                    else:
                        self.property_set.extend( list(prop) )
                               
            elif child.tag == "{DAV:}remove":
                prop = child[0]
                if prop.tag == "{DAV:}prop":
                    if self.property_remove==None: 
                        self.property_remove = list(prop)
                    else:
                        self.property_remove.extend( list(prop) )
            else:
                raise
                
     
class Properties(dict):
    """ Properties request handler
        A dictionary like object that holds all object 
        proerties.
    """
    
    # dav default properties cannot be cahnged by client
    Default = [
            '{%s}creationdate' % DAV_NS, 
            '{%s}getlastmodified' % DAV_NS, 
            '{%s}resourcetype'% DAV_NS ,
            '{%s}getetag'% DAV_NS, 
            '{%s}getcontentlength'% DAV_NS,
            ]

    # dav properties that can be changed by client
    Dead = [
            '{%s}getcontenttype' % DAV_NS, 
            '{%s}displayname' % DAV_NS, 
            '{%s}getcontenlanguage'% DAV_NS ,
            ]

    # does not return by default propfind and cannot be 
    # cahnged by client
    Live = [
            '{%s}supportedlock' % DAV_NS, 
            '{%s}lockdiscovery' % DAV_NS, 
            '{%s}quota-available-bytes' % DAV_NS, 
            '{%s}quota-used-bytes' % DAV_NS, 
            ]

    def __init__(self, obj, adapter=None, locks=None):
        self._object = obj
        self.adapter = adapter
        self.locks   = locks
        if self.adapter!=None:
            self.update( self.adapter._values )       

        self["{DAV:}supportedlock"]=Supportedlock()
        if self.locks!=None:
            self["{DAV:}lockdiscovery"]=self.lockdiscovery()
            
        self.update(self._object.properties())
            
    def lockdiscovery(self):
        active_list=[]
        for lock in self.locks:
            active_list.append(lock.Activelock())
        return LockDiscovery(*(active_list))

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def __setitem__(self, key, val):
        if val == None or isinstance (val, _Element):
            # if this is an element just append to dict
            dict.__setitem__(self, key, val)       
        elif hasattr(self._object, val):
            # if this is an object do method
            method = getattr(self._object, val)
            dict.__setitem__(self, key, method())       
        elif self.adapter and isinstance(val, str): 
            # if it is a string update value in database 
            if self.adapter.update_property (key, val):
                value = etree.fromstring(val)
                dict.__setitem__(self, key, value)         
            
    def __delitem__(self, key):
        if self.adapter != None:
            if self.adapter.delete_property(key):
                dict.__delitem__(self, key) 
        else:
            dict.__delitem__(self, key) 
        
    def _allprop(self):
        props = []
        for name in self.Default:
            value = self.get(name, None)
            if value!=None:
                props.append(value)
            else:
                props.append(DavElementFactory(name))
        return tuple(props)

    def _prop_name(self):
        propnames = []
        for attr in self.Default:   
            propnames.append(DavElementFactory(attr))
        return [(HTTP_OK , propnames)]

    def _prop_find(self, prop_list=None):
        if not prop_list:
            return [(HTTP_OK , self._allprop())]

        propnotfound = [DavElementFactory(name) 
                        for name in prop_list if not name in self.keys()]         
        propfound = []      
        found = [name for name in prop_list if name in self.keys()]
        for name in found:
            value = self.get(name, None)
            if value!=None:
                propfound.append(value)
            else:
                propfound.append(DavElementFactory(name))
            
        return [(HTTP_OK,  propfound), (404, propnotfound)]
                
    def _prop_patch(self, prop_set=None, prop_remove=None):
        set_status = HTTP_OK
        set_list = []                  
        remove_status = HTTP_OK
        remove_list = []                  
        
        if prop_set:
            for p in prop_set:       
                name = split_qname( p.tag )
                if name!=None:
                    if name[0] == 'DAV:':
                        if not p.tag in self.Dead:
                            set_status = 403
                set_list.append( p )
                               
        if prop_remove:
            for p in prop_remove:       
                name = split_qname( p.tag )
                if name!=None:
                    if name[0] == 'DAV:':
                        if p.tag in self.Default or p.tag in self.Live:
                            remove_status = 403
                if p.tag in self.keys():
                    remove_list.append( p )

        # fail both if either one has failed
        if set_status!=HTTP_OK or remove_status!=HTTP_OK:
            if set_status==HTTP_OK:
                set_status = 424
            if remove_status==HTTP_OK:
                remove_status = 424
        else:
            #Ok, update properties
            for pset in set_list:
                self[pset.tag]=etree.tostring(pset)
            for prem in remove_list:
                del self[prem.tag]

        return [(set_status, set_list), (remove_status,  remove_list)]

    def __repr__(self):
        return dict.__repr__(self)

    def get(self, name, default=None):
        return dict.get(self, name, default)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).iteritems():
            self[k] = v

    def propfind(self, proplist=None, propname=False):
        if propname:
            response = self._prop_name()
        else:
            response = self._prop_find(proplist)
        return self.propstat( response )       

    def proppatch(self, prop_set=None, prop_remove=None):
        response = self._prop_patch( prop_set, prop_remove )
        return self.propstat( response )

    def propstat(self, response):
        prop_stat = []
        for code, items in response:
            if len(items)>0:
                stat_code = "HTTP/1.1 %d %s"%(code,  http_responses[code])
                stat_e = PropStatElement(
                        PropElement(*items),
                        DAVElement.status(stat_code))
                prop_stat.append(stat_e)
        return tuple( prop_stat )   


class Property():
    """ Just a wrapper for propery database row """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class DbAdapter():
    """ Database object user properties storage
        Manage all external object properties, and 
        MOVE COPY DELETE of object properties 
    """
    
    def __init__(self, database):
        self._db = database
        self._uri = None
        self._properties = None
        self._values = None

    def select(self, uri):
        """retrieves object properties for uri"""
        self._uri = uri

        values = []
        rowlist = []
        for row in self._db.iter(
            """\
            select id, uri, property_name, property_value from property 
            where uri = %s
            """, self._uri):
            p = Property(**row)
            try:
                value = etree.fromstring( p.property_value )
                values.append( (p.property_name, value) ) 
                rowlist.append( (p.property_name, p) )                
            except:
                pass
                
        self._properties = dict( rowlist ) 
        self._values = dict( values )
                
    def update_property(self, key, val):
        if self._properties and key in self._properties:
            return self.update_row(key, val)
        else:
            return self.insert_row(key, val)

    def delete_property(self, key):
        if self._properties and key in self._properties:
            return self.delete_row(key)
        return 0
        
    def delete_row (self, key):
        p = self._properties[key]
        success = self._dbupdate("""\
            delete from property 
            where id = %s
            """, 
            p.id)
        if success:
            del self._properties[key]    
        return success                  
                    
    def update_row (self, key, val):
        p = self._properties[key]
        success = self._dbupdate("""\
            update property 
            set property_value = %s 
            where id = %s
            """, 
            val, p.id)
        if success>0:
            p.property_value = val
        return success
            
    def insert_row (self, key, val):
        rowid = self._db.execute("""\
            insert into property (uri, property_name, property_value)  
            values (%s, %s, %s)
            """, 
            self._uri, key, val)
        if rowid>0:
            self.select_row( rowid )
        return rowid
            
    def select_row(self, rowid):
        row = self._db.get ("""\
            select id, uri, property_name, property_value
            from property
            where id = %s
            """, rowid)
        p = Property(**row)
        self._properties[p.property_name] = p
        
    def _dbupdate(self, query, *parameters):
        """Update query, returning the rows effected. 
           Should be a library function
        """
        cursor = self._db._cursor()
        try:
            self._db._execute(cursor, query, parameters)
            return cursor.rowcount
        finally:
            cursor.close()

    def copy_properties (self, from_uri, to_uri, like=''):
        """ delete old properties from destination 
            then copy all properties from source
        """
        select_insert = """INSERT INTO property 
            (uri, property_name, property_value) 
            SELECT REPLACE (property.uri, %s, %s), 
                property.property_name, 
                property.property_value 
            FROM property WHERE property.uri LIKE %s
            """ 
        self.delete_properties(to_uri, like)
        success = self._dbupdate(select_insert, from_uri, to_uri, from_uri+like)
        return success        

    def move_properties (self, from_uri, to_uri, like=''):
        """ move properties to new uri """
        select = """UPDATE property 
            SET uri = REPLACE(uri, %s, %s) 
            WHERE uri LIKE %s
            """ 
        success = self._dbupdate(select, from_uri, to_uri, from_uri+like)
        return success        

    def delete_properties (self, uri, like=''):
        """ delete properties of uri"""
        select = """DELETE FROM property 
            WHERE uri LIKE %s
            """ 
        success = self._dbupdate(select, uri+like)
        return success        

    def copy_collection (self, from_uri, to_uri, like=''):
        self.copy_properties( from_uri, to_uri, like='%' )
    
    def move_collection (self, from_uri, to_uri, like=''):
        self.move_properties( from_uri, to_uri, like='%' )
    
    def delete_collection (self, from_uri, like=''):
        self.delete_properties( from_uri, like='%' )


                                   


