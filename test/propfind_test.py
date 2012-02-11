import unittest

from http.dav.davelement import *
from http.dav.properties import Properties, PropFindParser
from http.file_object import FileObject

class TestPropfind ( unittest.TestCase ):
    def test_default(self):
        file_object = FileObject(None, 'static', '')
        p = Properties( file_object )
        
        response = p.propfind()

        assert len ( response ) == 1
        assert response[0].tag == '{DAV:}propstat'
        childs = list( response[0] )
        assert len ( childs ) == 2
        assert childs[0].tag == '{DAV:}prop'
        assert childs[1].tag == '{DAV:}status'
        assert childs[1].text == 'HTTP/1.1 200 OK'

        props = list (childs[0])
        result = {}
        for prop in props:
            result[prop.tag] = prop.text
            
        assert '{DAV:}getlastmodified' in result.keys()
        assert result['{DAV:}getlastmodified']!=None
        assert '{DAV:}creationdate' in result.keys()
        assert result['{DAV:}creationdate']!=None
        assert '{DAV:}getcontentlength' in result.keys()
        assert result['{DAV:}getcontentlength']!=None
        assert '{DAV:}resourcetype' in result.keys()
        assert result['{DAV:}resourcetype']==None
        assert '{DAV:}getetag' in result.keys()
        assert result['{DAV:}getetag']!=None


        response = p.propfind(propname=True)
        assert response[0].tag == '{DAV:}propstat'
        childs = list( response[0] )
        assert len ( childs ) == 2
        assert childs[0].tag == '{DAV:}prop'
        assert childs[1].tag == '{DAV:}status'
        assert childs[1].text == 'HTTP/1.1 200 OK'
        props = list (childs[0])
        result = {}
        for prop in props:
            result[prop.tag] = prop.text
            
        assert '{DAV:}getlastmodified' in result.keys()
        assert result['{DAV:}getlastmodified']==None
        assert '{DAV:}creationdate' in result.keys()
        assert result['{DAV:}creationdate']==None
        assert '{DAV:}getcontentlength' in result.keys()
        assert result['{DAV:}getcontentlength']==None
        assert '{DAV:}resourcetype' in result.keys()
        assert result['{DAV:}resourcetype']==None
        assert '{DAV:}getetag' in result.keys()
        assert result['{DAV:}getetag']==None

    def test_parser(self):
        doc = """\
    <D:propfind xmlns:D="DAV:">
      <D:prop>
        <D:getlastmodified/>
        <D:creationdate/>
        <D:getcontentlength/>
        <D:getcontenttype/>
        <D:resourcetype/>
        <D:displayname/>
        <D:getetag/>
        <R:author xmlns:R="http://www.foo.bar/boxschema/" />
      </D:prop>
    </D:propfind>
    """
        parser = PropFindParser(doc)    
        file_object = FileObject(None, 'static', '')
        p = Properties( file_object )       
        response = p.propfind(parser.prop_list)
        #print etree.tostring(MultistatusElement(*response), pretty_print=True)
        
        assert len ( response ) == 2
        assert response[0].tag == '{DAV:}propstat'
        childs = list( response[0] )
        assert len ( childs ) == 2
        assert childs[0].tag == '{DAV:}prop'
        assert childs[1].tag == '{DAV:}status'
        assert childs[1].text == 'HTTP/1.1 200 OK'

        props = list (childs[0])
        result = {}
        for prop in props:
            result[prop.tag] = prop.text
            
        assert '{DAV:}getlastmodified' in result.keys()
        assert result['{DAV:}getlastmodified']!=None
        assert '{DAV:}creationdate' in result.keys()
        assert result['{DAV:}creationdate']!=None
        assert '{DAV:}getcontentlength' in result.keys()
        assert result['{DAV:}getcontentlength']!=None
        assert '{DAV:}resourcetype' in result.keys()
        assert result['{DAV:}resourcetype']==None
        assert '{DAV:}getetag' in result.keys()
        assert result['{DAV:}getetag']!=None

        assert response[1].tag == '{DAV:}propstat'
        childs = list( response[1] )
        assert len ( childs ) == 2
        assert childs[0].tag == '{DAV:}prop'
        assert childs[1].tag == '{DAV:}status'
        assert childs[1].text == 'HTTP/1.1 404 Not Found'
        
        props = list (childs[0])
        result = {}
        for prop in props:
            result[prop.tag] = prop.text
        assert '{DAV:}displayname' in result.keys()
        assert '{http://www.foo.bar/boxschema/}author' in result.keys()
        

if __name__ == '__main__':
    unittest.main()







