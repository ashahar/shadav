import unittest
from http.dav.lock import *


class TestLock ( unittest.TestCase ):


    def test_parser(self): 
        lockinfo="""\
        <lockinfo xmlns='DAV:'>
        <lockscope><exclusive/></lockscope>
        <locktype><write/></locktype></lockinfo>
        """
    
        p = LockParser(lockinfo)
        self.assertEqual( p.lockscope, 1)
        self.assertEqual( p.locktype, 'write')
        self.assertEqual( p.owner, None )
        
        
    def test_exclusive(self):
        lock = Lockdb()

        # check exclusive with depth infinity
        args = {'resource': u'/webdav/test1/', 'created': 1326985790L, 'depth': None, 'token': u'27e1fde165a57fc386711ad6ffe91a7207e2dd39', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 1L, 'id': 373L}
        lock._locks = [Lock (**args),]
        
        l = lock.all_locks('/webdav/test1/t.txt')
        assert l!=[]
        l = lock.all_locks('/webdav/test1/')
        assert l!=[]
        l = lock.shared_lock('/webdav/test1/t.txt')
        assert l==[]
        l = lock.conflict_lock('/webdav/')
        assert l!=[]
        l = lock.dependent_lock('/webdav/')
        assert l!=[]
        
        # check exclusive with depth 0
        args = {'resource': u'/webdav/test1/', 'created': 1326985790L, 'depth': 0, 'token': u'27e1fde165a57fc386711ad6ffe91a7207e2dd39', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 1L, 'id': 373L}
        lock._locks = [Lock (**args),]
        
        l = lock.all_locks('/webdav/test1/t.txt')
        assert l==[]
        l = lock.all_locks('/webdav/test1/')
        assert l!=[]
        l = lock.shared_lock('/webdav/test1/t.txt')
        assert l==[]
        l = lock.conflict_lock('/webdav/')
        assert l!=[]
        l = lock.dependent_lock('/webdav/')
        assert l!=[]


        # check exclusive on resource
        args = {'resource': u'/webdav/test1/t.txt', 'created': 1326985790L, 'depth': 0, 'token': u'27e1fde165a57fc386711ad6ffe91a7207e2dd39', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 1L, 'id': 373L}
        lock._locks = [Lock (**args),]
        
        l = lock.all_locks('/webdav/test1/t.txt')
        assert l!=[]
        l = lock.all_locks('/webdav/test1/')
        assert l==[]
        l = lock.shared_lock('/webdav/test1/t.txt')
        assert l==[]
        l = lock.conflict_lock('/webdav/')
        assert l!=[]
        l = lock.dependent_lock('/webdav/')
        assert l!=[]


    def test_shared(self):
        lock = Lockdb()

        # check shared with depth infinity
        args = {'resource': u'/webdav/test1/', 'created': 1326985790L, 'depth': None, 'token': u'27e1fde165a57fc386711ad6ffe91a7207e2dd39', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 0L, 'id': 373L}
        lock._locks = [Lock (**args),]
        
        l = lock.all_locks('/webdav/test1/t.txt')
        assert l!=[]
        l = lock.all_locks('/webdav/test1/')
        assert l!=[]
        l = lock.shared_lock('/webdav/test1/t.txt')
        assert l!=[]
        l = lock.conflict_lock('/webdav/')
        assert l==[]
        l = lock.dependent_lock('/webdav/')
        assert l!=[]
        
        # check shared with depth 0
        args = {'resource': u'/webdav/test1/', 'created': 1326985790L, 'depth': 0, 'token': u'27e1fde165a57fc386711ad6ffe91a7207e2dd39', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 0L, 'id': 373L}
        lock._locks = [Lock (**args),]
        
        l = lock.all_locks('/webdav/test1/t.txt')
        assert l==[]
        l = lock.all_locks('/webdav/test1/')
        assert l!=[]
        l = lock.shared_lock('/webdav/test1/t.txt')
        assert l==[]
        l = lock.conflict_lock('/webdav/')
        assert l==[]
        l = lock.dependent_lock('/webdav/')
        assert l!=[]


        # check shared on resource
        args = {'resource': u'/webdav/test1/t.txt', 'created': 1326985790L, 'depth': 0, 'token': u'27e1fde165a57fc386711ad6ffe91a7207e2dd39', 'timeout': None, 'owner': u'<D:href xmlns:D="DAV:">http://example.org/~ejw/contact.html</D:href>       ', 'scope': 0L, 'id': 373L}
        lock._locks = [Lock (**args),]
        
        l = lock.all_locks('/webdav/test1/t.txt')
        assert l!=[]
        l = lock.all_locks('/webdav/test1/')
        assert l==[]
        l = lock.shared_lock('/webdav/test1/t.txt')
        assert l!=[]
        l = lock.conflict_lock('/webdav/')
        assert l==[]
        l = lock.dependent_lock('/webdav/')
        assert l!=[]
        
        
