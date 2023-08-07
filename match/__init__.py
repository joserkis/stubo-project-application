"""
    stubo.match
    ~~~~~~~~~~~
    
    Matchers
     
    :copyright: (c) 2015 by OpenCredo.
    :license: GPLv3, see LICENSE for more details.
"""
import logging
import datetime
import copy
import json

from stubo.model.stub import Stub, StubCache
from stubo.exceptions import exception_response
from stubo.utils import as_date
from stubo.ext.transformer import transform

log = logging.getLogger(__name__)

def match(request, session, trace, system_date, url_args, hooks,
          module_system_date=None):
    """Returns the stats of a request match process
    :param request: source stubo request
    :param session: cached session payload associated with this request
    :param module_system_date: optional system date of an external module
    """
    request_text = request.request_body()
    scenario_key = session['scenario']
    session_name = session['session']
    log.debug(u'match: request_text={0}'.format(request_text))
    trace.info('system_date={0}, module_system_date={1}'.format(
        system_date, module_system_date))     
    stats = []
    
    if 'stubs' not in session or not len(session['stubs']):
        if session.get('status') != 'playback':
            raise exception_response(400,
                title="session {0} not in playback mode for scenario "
                "{1}".format(session_name, scenario_key))   
        raise exception_response(500,
          title="no stubs found in session {0} for {1}, status={2}".format(
                session_name, scenario_key, session.get('status')))
 
    stub_count = len(session['stubs'])
    trace.info(u'matching against {0} stubs'.format(stub_count))
    for stub_number in range(stub_count):
        trace.info('stub ({0})'.format(stub_number))
        stub = StubCache(session['stubs'][stub_number], scenario_key, 
                                session_name) 
        source_stub = copy.deepcopy(stub)
        request_copy = copy.deepcopy(request)
        stub, request_copy = transform(stub, 
                                  request_copy, 
                                  module_system_date=module_system_date, 
                                  system_date=system_date,
                                  function='get/response',
                                  cache=session.get('ext_cache'),
                                  hooks=hooks,
                                  stage='matcher',
                                  trace=trace,
                                  url_args=url_args)
        trace.info('finished transformation')
        if source_stub != stub:
            trace.diff('stub ({0}) was transformed'.format(stub_number), 
                       source_stub.payload, stub.payload)
            trace.info('stub ({0}) was transformed into'.format(stub_number),
                       stub.payload)
        if request_copy != request:
            trace.diff('request was transformed', request_copy.request_body(), 
                       request.request_body())
            trace.info('request was transformed into', request_copy.request_body())
                                                                            
        matcher = StubMatcher(trace)
        hits = matcher.match(request_copy, stub)
        stats.append(((hits, stub_number), stub))
                     
        if hits == stub.number_of_matchers():
            #  without most_matchers_win support
            trace.info(u"stub '{0}' matched".format(stub_number))
            break 
    # sort by hits (desc), stub_number (asc)
    # to match against 1. greatest hits or 2. first stub to get a hit
    return sorted(stats, key=lambda k: (k[0][0], -k[0][1]), reverse=True)

class Contains(object):
    
    def eval(self, x, y):
        """x in y?
        x and y should both be unicode
        """
        x = u''.join(x.split()).strip()
        y = u''.join(y.split()).strip()
        return y.find(x) >= 0
    
class StubMatcher(object):
    
    def __init__(self, trace):
        self.trace = trace
    
    def match(self, request, stub):
        """Match request with single stub"""
        # TODO: go through all the possible match specifiers when available                      
        request_text = request.request_body()                           
        matchers = stub.contains_matchers()
        num_matchers = len(matchers)                                                                                    
        hits = 0
        for i in range(num_matchers):
            self.trace.info('matcher ({0})'.format(i))
            matcher = matchers[i]
            if Contains().eval(matcher, request_text):
                hits += 1
                self.trace.info('matched', matcher)
            else:
                # all matchers need to match to get a hit
                hits = 0
                self.trace.warn('not matched')                                            
                break
        return hits                               
                    
                    
        
        