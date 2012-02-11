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


from lxml.builder import ElementMaker
from httplib import responses as http_responses

DAV_NS="DAV:"     
DAVElement = ElementMaker(namespace=DAV_NS, nsmap={'d' : DAV_NS})                  

"""Default DAV XML elements"""
MultistatusElement = DAVElement.multistatus
ResponseElement = DAVElement.response
PropStatElement = DAVElement.propstat
PropElement = DAVElement.prop
StatusElement = DAVElement.status
HrefElement = DAVElement.href
CollectionElement = DAVElement.collection
ErrorElement = DAVElement.error

"""Factory class for elements
"""
class DavElementFactory(object):
    def __init__(self, tag):
        self.tag = tag

    def __call__(self, *children, **attrib):
        return DAVElement(self.tag, *children, **attrib)

def get_response(href,code,error=None,description=None):
    """Constract basic response element
    """
    response = []
    href = HrefElement(href)
    response.append(href)
    status = StatusElement ("HTTP/1.1 %d %s"%(code,  http_responses[code]))
    response.append(status)
    if error!=None:
        response.append(ErrorElement (error))
    return ResponseElement(*(response))


