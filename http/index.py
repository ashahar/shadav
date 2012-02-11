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
import urllib
from lxml import etree
from tornado import version as server_version
from dav import version as dav_version


XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
XHTML = "{%s}" % XHTML_NAMESPACE

def collection_index( request, collection ):
    """ An Index like html response for get request
        on a collection.
    """
    
    xhtml = etree.Element(XHTML + "html", nsmap={None : XHTML_NAMESPACE} )
    xhtml.set("lang", "en")
    name = urllib.url2pathname(collection.uri).decode('utf-8')
    
    # Html header, title, meta, style
    head_e  = etree.SubElement(xhtml, XHTML + "head") 
    meta_e  = etree.SubElement(head_e, XHTML + "meta") 
    meta_e.set("http-equiv", "Content-Type")
    meta_e.set("content", "text/html; charset=UTF-8")       
    title_e = etree.SubElement(head_e, XHTML + "title") 
    title_e.text = "Direcory Index of %s" % name
    style_e = etree.SubElement(head_e, XHTML + "style") 
    style_e.set ("type", "text/css")
    style_e.text = "body { Font-family: arial }"
    body_e  = etree.SubElement(xhtml, XHTML + "body")

    # Page header
    h1_e    = etree.SubElement(body_e, XHTML + "h1")
    h1_e.text = "Direcory Index of %s" % name

    # Table
    table_e = etree.SubElement(body_e, XHTML + "table")

    # Table header
    row = etree.SubElement(table_e, XHTML + "tr")
    col = etree.SubElement(row, XHTML + "th")
    col.text = "Name"
    col = etree.SubElement(row, XHTML + "th")
    col.text = "Size"
    col = etree.SubElement(row, XHTML + "th")
    col.text = "Last Modified"

    # Line seperator
    row = etree.SubElement(table_e, XHTML + "tr")
    col = etree.SubElement(row, XHTML + "td")
    col.set ("colspan", "3")
    th = etree.SubElement(col, XHTML + "hr")          

    # Parent row reference      
    if (collection.get_parent()!=''):
        row = etree.SubElement(table_e, XHTML + "tr")
        col = etree.SubElement(row, XHTML + "td")
        col.set ("colspan", "3")
        href = etree.SubElement(col, "a")
        parent_uri = request.protocol + '://' + \
                 request.host + '/' + \
                 collection.get_parent()
        href.set("href", parent_uri)
        href.text = ".."

    # Table rows    
    for obj in collection.childs():
        row = etree.SubElement(table_e, XHTML + "tr")
        col = etree.SubElement(row, XHTML + "td")

        href = etree.SubElement(col, "a")
        href.set("href", obj.uri)
        href.text = os.path.basename(obj.filename).decode('utf-8')
        
        col = etree.SubElement(row, XHTML + "td")
        if obj.is_collection():
            col.text = '-'
        else:
            col.text = obj.getcontentlength().text                
        col = etree.SubElement(row, XHTML + "td")
        col.text = obj.lastmodified()

    # Line seperator
    row = etree.SubElement(table_e, XHTML + "tr")
    col = etree.SubElement(row, XHTML + "td")
    col.set ("colspan", "3")
    th = etree.SubElement(col, XHTML + "hr")          

    # Page footer
    version_e = etree.SubElement(body_e, XHTML + "h4")
    version_e.text = "Tornado/%s Server/%s on %s" % (server_version, dav_version, 
        os.uname()[0] + ' ' + os.uname()[3])
    return etree.tostring(xhtml, pretty_print=True)

