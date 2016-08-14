#!/usr/bin/env python
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
import ssl

import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.options
from tornado.options import define, options
from torndb import Connection

from handler import BasicHandler, RootHandler, ObjectHandler
from auth import DigestAuth, BasicAuth, DbSqlAuth, DbFileAuth
from dav.lock import Lockdb
from file_object import FileObject

CONFIG_FILE = 'dav-server.conf'

define("port", default=8888, help="run on the given port", type=int)
define("root", default='/tmp', help="Data root directory")
define("mysql_host", default='localhost', help="Main application DB host")
define("mysql_name", default='db1', help="Main application DB name")
define("mysql_user", default='admin', help="Main application DB user")
define("mysql_passwd", default='admin', help="Main application DB password")
define("realm", default='davserver', help="Sever authorization realm")
define("auth_type", default='', help="digest or basic")
define("auth_file", default='MYSQL', help="MYSQL or authentication file name")
define("use_ssl", default=False, help="Use SSL encryption", type=bool)
define("ssl_cretfile", default='', help="SSL certificate file")
define("ssl_keyfile", default='', help="SSL key file")
define("max_upload", default=0, help="Max file size to upload", type=int)


class DavApplication(tornado.web.Application):
    def __init__(self, root_directory, userauth, db, settings):    
        tornado.web.Application.__init__(self, [
            (r'/', BasicHandler),
            (r'/([^/]+)$', RootHandler),
            (r'/(.+)/', ObjectHandler),
            (r'/(.+)/(.+)', ObjectHandler),
        ], **settings)

        self.auth = userauth
        self.directory = os.path.abspath(root_directory)
        self.db = db
        self.lockdb = Lockdb(db)
        self._object = FileObject        
        self.max_upload = options.max_upload
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)


def run_server(conf_root=''):       
    conf_file = os.path.abspath(
                os.path.join (conf_root, CONFIG_FILE))
    if os.path.exists(conf_file):            
        tornado.options.parse_config_file( conf_file )
    tornado.options.parse_command_line()

    db = Connection(options.mysql_host, 
        options.mysql_name, 
        options.mysql_user, 
        options.mysql_passwd)

    usersdb = {}        
    if options.auth_file == 'MYSQL':
        users = DbSqlAuth(options.realm, db)
        usersdb = users._usersdb
    else:
        auth_file = os.path.abspath(
                os.path.join (conf_root, options.auth_file) )
        if os.path.exists(auth_file):
            users = DbFileAuth(options.realm, auth_file)
            usersdb = users._usersdb
                
    if options.auth_type == 'basic':
        auth = BasicAuth (usersdb, options.realm)
    elif options.auth_type == 'digest':
        auth = DigestAuth (usersdb, options.realm)
    else:
        auth = None
   
    settings = {
            "static_path": os.path.join(os.path.dirname(__file__), "static"),
    }

    application = DavApplication (options.root, auth, db, settings)
 
    use_ssl = options.use_ssl
    if use_ssl:
        ssl_options=dict(
        certfile=options.ssl_cretfile,
        keyfile=options.ssl_keyfile,
        )
        http_server = tornado.httpserver.HTTPServer(application, ssl_options = ssl_options)
    else:
        http_server = tornado.httpserver.HTTPServer(application)
    
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__=='__main__':
    run_server()
    
    









