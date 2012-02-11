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

import re
import time
import hashlib
from lxml import etree
from davelement import *


def get_current_time():    
    return int(time.mktime (time.localtime()))
        
EXCLUSIVE = 1
SHARED = 0
MAX_TIMEOUT = 3600*24*7

def Supportedlock ():
    return DAVElement.supportedlock(
            DAVElement.lockentry (
                DAVElement.lockscope(DAVElement.exclusive), 
                DAVElement.locktype(DAVElement.write)
            ),          
            DAVElement.lockentry (
                DAVElement.lockscope(DAVElement.shared), 
                DAVElement.locktype(DAVElement.write)
                )
            )
            
LockDiscovery = DAVElement.lockdiscovery

class Lock(object):
    def __init__(self, **kwargs): 
        self.__dict__.update(kwargs)

    def Activelock(self, root=None):
        activelock = []
        activelock.append( DAVElement.locktype(DAVElement.write) )

        if self.scope == EXCLUSIVE:
            lockscope = DAVElement.lockscope(DAVElement.exclusive)
        else:
            lockscope = DAVElement.lockscope(DAVElement.shared)
        activelock.append ( lockscope )

        if self.depth!=None:
            lockdepth = DAVElement.depth(str(self.depth))
        else:
            lockdepth = DAVElement.depth('Infinity')
        activelock.append ( lockdepth )

        if self.timeout!=None:
            diff = str ( self.created + self.timeout - get_current_time() )
            locktimeout = DAVElement.timeout('Second-' + diff)
        else:
            locktimeout = DAVElement.timeout('Infinite')   
        activelock.append ( locktimeout )
        
        token = DAVElement.locktoken( 
            DAVElement.href("opaquelocktoken:" + self.token) )      
        activelock.append ( token )

        if self.owner!=None:
            try:
                v = etree.fromstring(self.owner)
            except:
                v = self.owner
            lockowner = DAVElement.owner(v)   
            activelock.append ( lockowner )
        
        if root!=None:
            root_url = DAVElement.root( DAVElement.href(root + self.resource) )
            activelock.append ( root_url )
           
        return DAVElement.activelock( *activelock )


class Lockdb(object):
    
    def __init__(self, database=None):
        self._db = database
        self._locks = []
        if self._db:
            self.clean()
            self.select_locks()

    def getbyid(self, lockid):
        """finds a lock by id"""
        for lock in self._locks:
            if lock.id==lockid:
                return lock
        return None
       
    def getbytoken(self, token):
        """finds a lock by token"""
        for lock in self._locks:
            if lock.token==token:
                return lock
        return None

    def clean(self):
        self._db.execute("""\
            DELETE FROM locks WHERE 
            timeout IS NULL AND created + %s < UNIX_TIMESTAMP() OR 
            timeout IS NOT NULL AND created + timeout < UNIX_TIMESTAMP();
        """, MAX_TIMEOUT)  
        
    def select_locks(self):
        self._locks = []
        for row in self._db.iter("""\
            SELECT id, resource, token, scope, depth, owner, created, timeout
            FROM locks WHERE 
            timeout IS NULL OR created + timeout > %s""", get_current_time() ):
            self._locks.append(Lock(**row))

    def add_lock(self, resource, scope=1, depth=0, timeout=None, owner=None):
        """ resource: The resource to be locked
            scope   : 1 = exclusive 0 = shared
            depth   : None = infinity
            timeout : None = infinite
        """
        created = get_current_time()  
        lock_token = hashlib.sha1(resource + str(created)).hexdigest()
        rowid = self._db.execute("""\
            insert into locks (resource, token, scope, depth, created, timeout, owner)  
            values (%s, %s, %s, %s, %s, %s, %s)
            """, resource, lock_token, scope, depth, created, timeout, owner)

        if rowid>0:
            self.select_locks()
        return rowid

    def refresh_lock(self, lockid, timeout):
        created = get_current_time()  
        self._db.execute("update locks set created = %s, timeout = %s where id = %s",
                         created, timeout, lockid)       
        self.select_locks()

    def remove_lock(self, lockid):
        self._db.execute("delete from locks where id = %s",
                         lockid)       
        self.select_locks()

    def all_locks(self, resource):     
        """ retrun a list of all locks associated with resource"""
        any_lock = [lock for lock in self._locks if \
                not self.isexpired(lock) and \
                self.islocked(resource, lock.resource, lock.depth)]
        return any_lock

    def exclusive_lock(self, resource):
        """ retrun a list of exclusive locks associated with resource"""   
        exclusive_lock = [lock for lock in self._locks if \
                not self.isexpired(lock) and lock.scope == EXCLUSIVE and \
                self.islocked(resource, lock.resource, lock.depth)]
        return exclusive_lock

    def shared_lock(self, resource):
        """ retrun a list of shared locks associated with resource"""   
        shared_lock = [lock for lock in self._locks if \
                not self.isexpired(lock) and lock.scope == SHARED and \
                self.islocked(resource, lock.resource, lock.depth)]
        return shared_lock

    def conflict_lock(self, resource):
        """ retrun a list of exclusive locks on childs of resource
        """   
        conflict_lock = [lock for lock in self._locks if \
            lock.resource!=resource and \
            not self.isexpired(lock) and \
            lock.scope == EXCLUSIVE and \
            self.islocked(lock.resource, resource, None)]
        return conflict_lock

    def dependent_lock(self, resource):
        """ retrun a list of all locks on childs of resource
        """   
        dependent_lock = [lock for lock in self._locks if \
            lock.resource!=resource and \
            not self.isexpired(lock) and \
            self.islocked(lock.resource, resource, None)]
        return dependent_lock

    def isexpired(self, lock):
        """ return True if lock is expired,
            none is never expire
        """ 
        if lock.timeout == None:
            return False
        return lock.created + lock.timeout < get_current_time()

    def islocked(self, resource, path, depth):
        """return True if:
            path is equal to resource if depth is 0
            path is parent of resource and depth is infinity 
        """
        return ( (depth == 0 and path == resource) or \
                 (depth == None and re.match(path, resource)!=None) )

      
class LockParser:
    def __init__(self, xdoc):
        root = etree.fromstring(xdoc)
        self.lockscope = None
        self.locktype  = None
        self.owner     = None
        childs = list (root)
        for child in childs:
            if child.tag=="{DAV:}lockscope":
                if child[0].tag=="{DAV:}shared":
                    self.lockscope = SHARED
                elif child[0].tag=="{DAV:}exclusive":
                    self.lockscope = EXCLUSIVE
                else:
                    raise
            elif child.tag=="{DAV:}locktype":
                if child[0].tag=="{DAV:}write":
                    self.locktype="write"
                else:
                    raise
            elif child.tag=="{DAV:}owner":
                if len(list(child))>0:
                    self.owner = etree.tostring(child[0])
                else:
                    self.owner = child.text
            else:
                raise


def parse_timeout(header):
    """ Timeout header parser
        TimeOut = "Timeout" ":" 1#TimeType
        TimeType = ("Second-" DAVTimeOutVal | "Infinite")
        DAVTimeOutVal = 1*DIGIT
        
        set to infinite timeout if cannot comply with client requast
        return None for infinite
    """
    timeoutre = re.compile(r'(Infinite|Second-(\d+))')
    match = timeoutre.findall( header )
    timeout = -1
    for ti in match:
        if ti[0].startswith('Second'):
            t = int (ti[1])
            if t>timeout:
                timeout = t
    if timeout>MAX_TIMEOUT:
        return MAX_TIMEOUT
    if timeout==-1:
        return None
    return timeout




