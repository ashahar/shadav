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
import hashlib
import shutil
import urllib
import calendar
import time
import mimetypes
from datetime import datetime
from email.utils import formatdate

from dav.davobject import DavObject

class FileObject(DavObject):
    """ Dav file object method implementation
    """

    def __init__(self, appliction, parent='', name=''):
        DavObject.__init__(self, appliction, parent, name)
        self.filename = os.path.abspath(
            os.path.join(self.root, self.parent, self.name))
        self.uri = urllib.pathname2url ('/' + os.path.join(self.parent, self.name))
        self.exists = os.path.exists(self.filename) 

        if self.exists:
            stat = os.stat(self.filename) 
            self.collection = os.path.isdir(self.filename)
            self.st_mtime = stat.st_mtime
            self.st_ctime = stat.st_ctime
            self.st_size  = stat.st_size
            self.etag = '"%s"' % hashlib.sha1(
                    self.filename + self.lastmodified()).hexdigest() 
        else:
            t = calendar.timegm(time.gmtime())
            l = formatdate(t, localtime=True, usegmt=True)
            self.etag = '"%s"' % hashlib.sha1(self.filename + l).hexdigest() 

    @staticmethod
    def fromuri_factory(application, uri):
        filename = urllib.url2pathname(uri[1:])
        name = os.path.basename(filename)
        if name!='':
            parent,n = os.path.split(filename)
        else:
            parent = filename
        return FileObject(application, 
                parent = parent, 
                name = name)
          
    def contenttype(self):
        """ guess content type """
        mtype =  "application/unknown"
        guess = mimetypes.guess_type(self.filename)
        if guess[0]!=None:
            mtype = guess[0]
        return mtype

    def get_parent(self):
        """ return the parent uri of a collection """
        p, n = os.path.split(self.parent)
        if p!='':
            p = urllib.pathname2url(p)
        return p
                                  
    def childs(self):
        """ return a list of childs of this resource
        """
        childs = []
        if self.collection:               
            for name in os.listdir(self.filename):
                filename = os.path.join(self.root, self.parent , name)
                path = os.path.abspath(filename)
                if os.path.isdir(path):
                    obj = FileObject(self.application, 
                        parent = os.path.join(self.parent, name))
                else:
                    obj = FileObject(self.application, 
                        parent = self.parent, 
                        name = name)
                childs.append( obj )
        return childs

    def mkcol(self):
        """ Dav mkcol method
        """
        parent,name = os.path.split(self.parent)   
        parent_file = os.path.abspath(
            os.path.join(self.root, parent))
        if not os.path.isdir(parent_file):
            return 409
        try:
            os.makedirs(self.filename)
        except (IOError, os.error), why:
            return 500  
        return 201

    def copy(self, destination, overwrite=None):
        """ Dav file copy method
        """
        rc = 201           
        if self.collection:        
            if os.path.isdir(destination):
                if overwrite=='F':
                    return 412
                try:
                    shutil.rmtree(destination)
                except (IOError, os.error), why:
                    return 500
                    
            try:
                os.makedirs(destination)
            except (IOError, os.error), why:
                return 500

            names = os.listdir(self.filename)
            for name in names:
                srcname = os.path.join(self.filename, name)
                dstname = os.path.join(destination, name)
                try:
                    if os.path.islink(srcname):
                        pass
                    elif os.path.isdir(srcname):
                        shutil.copytree(srcname, dstname)
                    else:
                        shutil.copy2(srcname, dstname)
                except (IOError, os.error), why:
                    return 500        
        else:
            if os.path.exists( destination ):
                if os.path.isfile( destination ):
                    if overwrite=='F':
                        return 412
                rc = 204               
                    
            p, n = os.path.split(destination)
            if not os.path.isdir(p):
                return 409

            try:
                shutil.copy2(self.filename, destination)
            except (IOError, os.error), why:
                return 500

        return rc
        
    def move(self, destination, overwrite=None):
        """ Dav file move method
        """
        rc = 201           
        if self.collection:        
            if os.path.exists(destination):
                if overwrite!='T':
                    return 412
                if os.path.isdir( destination ):
                    try:
                        shutil.rmtree( destination )
                    except (IOError, os.error), why:
                        return 500
                else:
                    try:
                        os.unlink( destination )
                    except (IOError, os.error), why:
                        return 500

            try:
                os.makedirs(destination)
            except (IOError, os.error), why:
                return  500

            names = os.listdir(self.filename)
            for name in names:
                srcname = os.path.join(self.filename, name)
                dstname = os.path.join(destination, name)
                try:
                    shutil.move(srcname, dstname)
                except (IOError, os.error), why:
                    return 500        

            try:
                shutil.rmtree( self.filename )
            except (IOError, os.error), why:
                return 500

        else:
            if os.path.exists( destination ):
                if os.path.isfile(destination):
                    if overwrite!='T':
                        return 412
                rc = 204

            p, n = os.path.split(destination)
            if not os.path.isdir(p):
                return 409

            try:
                shutil.move(self.filename, destination)
            except (IOError, os.error), why:
                return 500

        return rc

    def delete(self):
        """ Dav file delete method
        """
        if self.collection: 
            try:    
                shutil.rmtree(self.filename)
            except (IOError, os.error), why:
                return 500           
        else:
            try:    
                os.unlink(self.filename)
            except (IOError, os.error), why:
                return 500
        return 204

    def write(self, body=''):        
        """ Dav write to file method
        """
        try:    
            object_file = open(self.filename, "w")
            try:
                object_file.write(body)
            finally:
                object_file.close()
        except IOError as (errno, strerror):
            pass
    
    def read(self):        
        """ Dav read method
        """
        try:
            object_file = open(self.filename, "r")
            try:
                return object_file.read()
            finally:
                object_file.close()
        except (IOError, os.error), why:
            pass
    
            
    
    
    

        
    

