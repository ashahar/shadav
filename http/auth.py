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
import hashlib
import time
import os


class DbSqlAuth(object):
    """ Database users mysql
    """
    def __init__(self, realm, database):
        self.realm = realm
        self._db = database
        
        user_list = []
        for row in self._db.iter("""\
            SELECT id, realm, user_name, user_hash
            FROM users"""):
            if row['realm'] == self.realm:
                user_list.append( (row['user_name'], row['user_hash']) )
        self._usersdb = dict( user_list )


class DbFileAuth(object):
    """ Database users file
    """
    def __init__(self, realm, filename):
        self.realm = realm
        users = []
        try:
            fd = open (filename, 'r')
            try:
                users = fd.readlines()
            finally:
                f.close()    
        except:
            pass
            
        user_list = []
        for user in users:
            u = user.rstrip().split(':')
            if len(u)!=3:
                continue
            if u[1] == self.realm:
                user_list.append( (u[0],u[2]) )
        self._usersdb = dict( user_list )


class Authenticate(object):
    def __init__(self, usersdb, realm, algorithm='MD5'):
        self.realm = realm
        self.usersdb = usersdb
        self.algorithm = algorithm
        if algorithm=='MD5':
            self._hash = hashlib.md5
        elif algorithm=='SHA':
            self._hash = hashlib.sha1
        else:
            raise

    def authenticate(self, request, autherization):
        return False

    def get_header(self):
        pass        

    def compute_hash(self, *args):
        s = ':'.join(args)
        return self._hash (s).hexdigest()


class BasicAuth(Authenticate):
    """ HTTP Basic authentication implementation
    """
    def __init__(self, usersdb, realm, algorithm='MD5'):
        Authenticate.__init__(self, usersdb, realm, algorithm)

    def authenticate(self, request, params):
        user, passwd = params.decode('base64').split(':', 1)
        h1 = self.usersdb.get(user,'')
        h2 = self.compute_hash(user, self.realm, passwd)
        if h1==h2:
            self.username = user  
            return True
        return False        

    def get_header(self):
        return 'Basic realm="%s"'%self.realm        


authm = re.compile (r'\s*(\w+)="?([^"]+)"?\s*')
class DigestAuth(Authenticate):
    """ HTTP Digest authentication implementation
    """

    def __init__(self, usersdb, realm, algorithm='MD5'):
        Authenticate.__init__(self, usersdb, realm, algorithm)
        self.opaque = self._hash("%d:%s"%(time.time(),self.realm)).hexdigest()

    def authenticate(self, request, params):
        parts = params.split(',')
        authp = []
        for p in parts:
            m = authm.match(p)
            if m!=None:
                authp.append (m.groups())     
        if authp==[]:
            return False                  
        auth_param = dict (authp)
        return self._authenticate( request, **auth_param )

    def _authenticate(self, request, **kw):
        user = kw.get('username')
        hA1 = self.usersdb.get(user,'')
        hA2 = self.compute_hash(request.method, kw.get('uri'))
        if 'auth' in kw.values():
            result = self.compute_hash(hA1, 
                kw.get('nonce'), 
                kw.get('nc'), 
                kw.get('cnonce'), 
                kw.get('qop'), 
                hA2)   
        else:
            result = self.compute_hash(hA1, kw.get('nonce'), hA2)

        if result == kw.get('response'):
            self.username = user  
            return True
        return False

    def get_header(self):
        challange = dict (
                realm = self.realm, 
                opaque = self.opaque, 
                nonce = os.urandom(8).encode('hex'), 
                algorithm = self.algorithm,
                qop = 'auth'
                )
        digest =  ','.join ([k + '="%s"'%v for k,v in  challange.items()])
        return 'Digest ' + digest



