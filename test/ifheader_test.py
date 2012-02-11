import unittest


from urlparse import urlsplit
import os


from http.ifheader import if_parse_header, evaluate_expression
from http.file_object import FileObject
from http.dav.lock import *

args1={'resource': u'/webdav/test/y111358.txt', 'created': 1326985790L, 'depth': 0L, 'token': u'27e1fde165a57fc386711ad6ffe91a7207e2dd39', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 1L, 'id': 373L}

args2={'resource': u'/webdav/test/y111348.txt', 'created': 1326985907L, 'depth': 0L, 'token': u'96fd22a9e5180c1055f6ce45ef66067d41d9fb92', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 1L, 'id': 374L}

lock_db = Lockdb()
lock_db._locks = [Lock(**args1),Lock(**args2),]
default = '/webdav/test/y111358.txt'
ETAG = "\"ddddffff1234\""


def _evaluate(conditions):
    results = {}
    for condition in conditions:
        if condition[0]!=None:
            urld = urlsplit (condition[0])
            locks = lock_db.all_locks(urld.path)
            uri = urld.path
        else:
            locks = lock_db.all_locks(default)
            uri = default

        lock_tokens = [lock.token for lock in locks] 
        result = evaluate_expression(lock_tokens, [ETAG], condition[1])
        if result!=None and result[0]:
            results[uri] = result[1]
    return results


class TestIfHeader ( unittest.TestCase ):

    def test_ifheader(self): 
        IF = [\
                """
                </webdav/test/y111358.txt>      
                (<opaquelocktoken:27e1fde165a57fc386711ad6ffe91a7207e2dd39>
                 [%s]) 
                """ % ETAG
            ]

        for h in IF:
            c = if_parse_header (h)
            p = _evaluate (c)
            self.assertTrue (p!={})
            self.assertTrue ('/webdav/test/y111358.txt' in p )

        IF = [\
            """(<opaquelocktoken:27e1fde165a57fc386711ad6ffe91a7207e2dd39>)
            """,               
            """(<opaquelocktoken:27e1fde165a57fc386711ad6ffe91a7207e2dd39>)
            """,
            """(<opaquelocktoken:27e1fde165a57fc386711ad6ffe91a7207e2dd39>)
            """,
            """(<opaquelocktoken:27e1fde165a57fc386711ad6ffe91a7207e2dd39> Not <DAV:no-lock>)
            """,
            """(<opaquelocktoken:27e1fde165a57fc386711ad6ffe91a7207e2dd40> Not <DAV:no-lock>)
            (<opaquelocktoken:27e1fde165a57fc386711ad6ffe91a7207e2dd39>)
            """,
            ]

        for h in IF:
            c = if_parse_header (h)
            p = _evaluate (c)
            self.assertTrue(p!={})
            self.assertTrue ('/webdav/test/y111358.txt' in p)

        IF =["""</webdav/test/c111358.txt>
             (<opaquelocktoken:xxxxe1fde165a57fc386711ad6ffe91a7207e2dd39>)
            """,
            """<http://localhost:8888/webdav/litmus/lockme>        
             (<opaquelocktoken:70b1696ac5ba692a861bb524d154cd36f909f12f>)
             [u'70b1696ac5ba692a861bb524d154cd36f909f12f'] /webdav/test/lock
             "2fe10ae13217ba8f80ae41d570614be01fb252af"
            """,
            ]

        for h in IF:
            c = if_parse_header (h)
            p = _evaluate (c)
            self.assertTrue(p=={})
                 
        IF = [\
            """(<opaquelocktoken:96fd22a9e5180c1055f6ce45ef66067d41d9fb92>)
            """,               
            """(<opaquelocktoken:96fd22a9e5180c1055f6ce45ef66067d41d9fb92>)
            """,
            """(<opaquelocktoken:96fd22a9e5180c1055f6ce45ef66067d41d9fb92> Not ["12344"])
            """,
            """(<DAV:no-lock>)
            """,
            ]

        for h in IF:
            c = if_parse_header (h)
            p = _evaluate (c)
            self.assertTrue(p=={})
        
                
        
if __name__ == '__main__':
    unittest.main()
        
        

