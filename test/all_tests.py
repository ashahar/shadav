import unittest

from ifheader_test import *
from propfind_test import *
from lock_test import *

def suite():
    suite = unittest.TestSuite = [
        unittest.TestLoader().loadTestsFromTestCase(TestIfHeader),
        unittest.TestLoader().loadTestsFromTestCase(TestPropfind),
        unittest.TestLoader().loadTestsFromTestCase(TestLock),
        ]
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(suite())        


