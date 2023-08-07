import unittest
import mock
from stubo.testing import make_stub, make_cache_stub, DummyModel, DummyQueue

class Test_match(unittest.TestCase):
    
    '''A stub consists of a list of matchers and a response that goes with them.
       A request will be evaluated against each matcher in each stub. the first
       matching stub wins and has its response returned to the calling program.'''  
    
    def setUp(self):
        self.first_2_session = {       
        "session": "first_2", 
        "scenario": "localhost:first",         
        'status' : 'playback',   
        "system_date": "2013-09-05",          
        'stubs' : [ 
            make_cache_stub(["get my stub"], [1]),
            make_cache_stub(["first matcher - will match",
                   "second matcher - will not match"], [2]),
            make_cache_stub(["this is a lot of xml or text..."], [3]),
            make_cache_stub(["get my stub", "today"], [4]),
            make_cache_stub(["one two three"], [5]),
            make_cache_stub(["one two three"], [6]),
            make_cache_stub(['text    with \r\n line feeds'], [7])
         ]
        }    
    
    def _get_best_match(self, request_text, session, trace=None,
                        system_date=None,
                        url_args=None, 
                        module_system_date=None): 
        from stubo.match import match
        from stubo.utils.track import TrackTrace
        trace = trace or TrackTrace(DummyModel(tracking_level='normal'), 
                                    'matcher')
        from stubo.model.request import StuboRequest
        request = StuboRequest(DummyModel(body=request_text, headers=dict()))
        url_args = url_args or {}
        from stubo.ext.transformer import StuboDefaultHooks
        results = match(request, session, trace, system_date, 
                        url_args,
                        StuboDefaultHooks(),
                        module_system_date=module_system_date)
        return results[0]       

    def test_match_simple_request(self):
        request = "get my stub"
        results = self._get_best_match(request, self.first_2_session)
        stub = results[1]                                        
        self.assertEquals(stub.response_ids(), [1])
        
    def test_match_simple_request_with_spaces(self):
        request = "get my         stub"
        results = self._get_best_match(request, self.first_2_session)
        stub = results[1]                             
        self.assertEquals(stub.response_ids(), [1])     

    def test_not_all_matchers_match(self):
        request = "first matcher - will match"
        results = self._get_best_match(request, self.first_2_session)
        hits = results[0]                                        
        self.assertFalse(hits[0])

    def test_find_text_anywhere_in_matcher(self):
        request = "this is a lot of xml or text... or even json"
        results = self._get_best_match(request, self.first_2_session)
        stub = results[1]                                            
        self.assertEquals(stub.response_ids(), [3])

    def test_match_fail(self):
        request = "it's not me"
        results = self._get_best_match(request, self.first_2_session)
        hits = results[0]                                        
        self.assertFalse(hits[0])

    def test_first_of_a_tie_wins(self):
        request = "one two three"
        results = self._get_best_match(request, self.first_2_session)
        stub = results[1]                                        
        self.assertEquals(stub.response_ids(), [5])

    def test_ignore_rubble_in_request(self):
        request = "Rubble in front, one two three. Rubble at the end."
        results = self._get_best_match(request, self.first_2_session)
        stub = results[1]                                         
        self.assertEquals(stub.response_ids(), [5])

    def test_matcher_with_line_feeds(self):
        request =  'text with \r\n line feeds'
        results = self._get_best_match(request, self.first_2_session)
        stub = results[1]                                            
        self.assertEquals(stub.response_ids(), [7])
        
    def test_matcher_with_no_stubs_and_not_playback_session_fails(self):
        from stubo.exceptions import HTTPClientError
        session = {              
            "session": "first_2", 
            "scenario": "localhost:first",         
            'status' : 'dormant', 
            "system_date": "2013-09-05",   
        } 
        with self.assertRaises(HTTPClientError):
            self._get_best_match("", session)  
        
    def test_matcher_with_no_stubs_and_playback_session_errors(self):
        from stubo.exceptions import HTTPServerError  
        session = {              
            "session": "first_2_playback", 
            "scenario": "localhost:first",         
            'status' : 'playback',   
            "system_date": "2013-09-05", 
        } 
        with self.assertRaises(HTTPServerError): 
            self._get_best_match("", session)           

class TestMatcherWithModule(unittest.TestCase):
    
    def setUp(self):
        self.q = DummyQueue
        self.q_patch = mock.patch('stubo.ext.module.Queue', self.q)
        self.q_patch.start()
        from stubo.ext.module import Module
        Module('localhost').add('dummy', exit_code)      
       
    def tearDown(self): 
        import sys
        test_modules = [x for x in sys.modules.keys() \
                        if x.startswith('localhost_stubotest')]
        for mod in test_modules:
            del sys.modules[mod]
            
        from stubo.ext.module import Module
        Module('localhost').remove('dummy')   
        self.q_patch.stop()         
        
    def test_match_eval_error(self): 
        from stubo.match import match
        from stubo.utils.track import TrackTrace
        trace = TrackTrace(DummyModel(tracking_level='normal'), 'matcher') 
        session = {       
            "session": "first_2", 
            "scenario": "localhost:first",         
            'status' : 'playback',   
            "system_date": "2013-09-05",         
            'stubs' : [   
                {"matchers" : [
                       "{{"],
                       "recorded": "2013-09-05", 
                       "response_id" : 5,
                       "module": {"system_date": "2013-08-07", "version": 1, 
                                  "name": "dummy"},
                }] 
            } 
        from stubo.exceptions import HTTPClientError
        from stubo.model.request import StuboRequest
        request = StuboRequest(DummyModel(body='xxx', headers={}))
        from stubo.ext.transformer import StuboDefaultHooks
        url_args = {}
        with self.assertRaises(HTTPClientError): 
            match(request, session, trace, session.get('system_date'), url_args, StuboDefaultHooks(), None)  
  

                      
exit_code = """
from stubo.ext.user_exit import GetResponse, ExitResponse

class Dummy(GetResponse):
    
    def __init__(self, request, context):
        GetResponse.__init__(self, request, context)        
                
    def doResponse(self):  
        return ExitResponse(self.request, self.stub)        
        
def exits(request, context):
    if context['function'] == 'get/response':
        return Dummy(request, context)
"""