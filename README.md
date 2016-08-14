This is an implementation of a webdav server based
entirely on python libraries.

It is tested to be working against windows 7 client nautilus cadaver and
passes the litmus test.

You will need the tornado libraries so install from your repository.

Currently the database backend is MySql so you'll need to install it,
create an empty database (see Mysql documentation) and then run the
schema.sql file.

The configuration file is pretty self explanatory just put in the
root directory of your files (see example).

If you want to put the configuration file somewhere else you'll need to edit
the dav-server.py file and give the directory of the configuration file as an
argumjent to the run-server call.

Create a directory under the root directory defined in the configuration file
for example /tmp/test/data/webdav/
This will be the base Dav server directory. 

Try to connect to:
http://localhost:8080/webdav/ from any client. 
You can also open it with your web browser.

By default authentication is disabled. 

If you want to use any authentication method you will need 
to create users in the database.
Currently you have to create users manualy e.g:
 
 INSERT INTO users (realm, user_name, user_hash) 
 VALUES ('realm', 'username', MD5('username:realm:password'));

Another possibility is using the htdigest apache utility for
creating users and supply the filename in the configuration file.
Then put the users file in your conf directory (default is
the current directory).

Change the authentication option in the configuration file to
basic or digest authentication.

To connect from Windows 7 explorer with authentication 
you have to use the digest authentication method.


