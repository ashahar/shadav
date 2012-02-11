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
from urlparse import urlsplit


"""
If header parser

If = "If" ":" ( 1*No-tag-list | 1*Tagged-list )

     No-tag-list = List
     Tagged-list = Resource-Tag 1*List

     List = "(" 1*Condition ")"
     Condition = ["Not"] (State-token | "[" entity-tag "]")

http://tools.ietf.org/html/rfc4918#section-10.4
"""

tokenm = re.compile(r'<opaquelocktoken:([0-9a-f\-]+)>')
etagm  = re.compile(r'\[(\"[\w\-]+\")\]')
def evaluate_condition(tokens, etags, condition):
    found = None
    f = False

    token = tokenm.match(condition[1])
    if token:
        if condition[0]=='Not':
            f = token.group(1) not in tokens 
        else:
            f = token.group(1) in tokens  
            found = token.group(1)
    else:
        etag = etagm.match(condition[1])
        if etag:
            if condition[0]=='Not':
                f = etag.group(1) not in etags 
            else:
                f = etag.group(1) in etags 
        else:
            if condition[1] == '<DAV:no-lock>':
                if condition[0]=='Not':
                    f = True
                else:
                    f = False
            else:  
                # not a leagal expression
                return None
    return (f, found)

def evaluate_expression(tokens, etags, conditions):
    """ Evalute list of "OR" expression each
        is a list of logical "AND" expressions
    """
    for and_condition in conditions:
        # loop over a condition to find a True expression 
        # and a valid token is exsits
        r = True
        out = []
        for condition in and_condition:
            f = evaluate_condition(tokens, etags, condition)
            if f==None:
                # invalid
                return None
            elif f[0]:
                # if we found a token add and continue
                if f[1]!=None:
                    out.append(f[1])
            else:
                r = False
                break
        # if Ture we can dismiss other conditions
        if r:
            return (True, out)            
    return (False, [])


tagged_list = re.compile(r'\s*(<.+?>)\s*(\(.+\))\s*', re.DOTALL)
no_tag_list = re.compile(r'\s*\((.+?)\)\s*', re.DOTALL)
conditionm  = re.compile(r'(Not)?\s*(<\w+:.*?>|\[.*?\])')

def parse_no_tag_list( chunk ):
    cond_list=[]
    no_tagged = no_tag_list.match(chunk)
    if no_tagged:
        while no_tagged:
            cond_list.append( no_tagged.group(1) )
            end_pos = no_tagged.end()
            no_tagged = no_tag_list.search( chunk, end_pos )

        if chunk[end_pos:]!='':
            # Bogus: chunk[end_pos:] should be empty
            return []
    return cond_list
        

def if_parse_header(header): 
    conditions = []
    tagged =  tagged_list.match( header )
    if tagged:
        while tagged:
            urim = re.match('<(.+)>', tagged.group(1))           
            uri = urim.group(1)            
            contidition_list=[]
            for c in parse_no_tag_list( tagged.group(2) ):
                condition = conditionm.findall (c) 
                contidition_list.append( condition )    
            conditions.append( (uri, contidition_list) )
            end_pos = tagged.end()
            tagged = tagged_list.match( header, end_pos )

        # Bogus: chunk[end_pos:] should be empty
        if header[end_pos:]!='':
            return []
    else:
        contidition_list=[]
        all_ = parse_no_tag_list(header)
        if all_!=[]:
            for c in all_:
                condition = conditionm.findall (c) 
                contidition_list.append( condition )    
            conditions.append( (None, contidition_list) )    
    return conditions


def if_header_evaluate(application, request):
    """ Evaluetes expression list

        The if header can evalute a lock token on resource, resource etag
        or any other True False expression. The expressions are a list of
        AND conditions which has OR relationaship between them.
       
        If a lock token is supplied the condition is evaluted against that token
        and if True then that lock token is returned in a list (can be more the one).
        because the if_header can contain a mapped list of uri's the return result
        is a dictionary of uri's that has evaluated to True. 
       
        - If no condition is True return empty dict
        - If no lock tokens are supplied but is True return empty list
        - If evaluted to True return the tokens as a list
        
        otherwise retrun None
    """
    if_header = request.headers.get('If')            
    if if_header == None:
        return None
        
    results = {}
    # condition is a list of list of AND expressions
    conditions = if_parse_header (if_header)
    for condition in conditions:
        if condition[0]!=None:
            urld = urlsplit (condition[0])
            uri = urld.path
        else:
            # default uri for unmapped list
            # can be only one list of conditions for 
            # the current resource
            uri = request.uri

        d = application._object.fromuri_factory(application, uri)
        if d.is_exists():
            locks = application.lockdb.all_locks(uri)
            lock_tokens = [lock.token for lock in locks] 
            # result can be None or a tuple where the first element is True or 
            # False and the second is a list of lock token that evalutes to True.
            # can be empty list if the condition is True but has no lock tokens.
            result = evaluate_expression(lock_tokens, [d.etag], condition[1])
            if result!=None and result[0]:
                results[d.uri] = result[1]
                
    return results
    
