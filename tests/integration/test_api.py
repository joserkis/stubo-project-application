# -*- coding: utf-8 -*-
import json
from stubo.testing import Base

class TestPutDelay(Base):   

    def test_put_fixed(self):
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
                               'name=rtz_1&delay_type=fixed&milliseconds=700'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"message": "Put Delay Policy Finished", 
                           u'status': 'new', "delay_type": "fixed",
                           "name": "rtz_1"}}
        self.assertEqual(payload, expect)
        self.assertTrue(int(response.request_time) < 5)

    def test_put_normalvariate(self):
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
            'name=rtz_2&delay_type=normalvariate&mean=100&stddev=50'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"message": "Put Delay Policy Finished", 
                           u'status': 'new', "delay_type": "normalvariate", 
                           "name": "rtz_2"}}
        self.assertEqual(payload, expect)
        self.assertTrue(int(response.request_time) < 5)

    def test_update_delay(self):
        from stubo.cache import Hash
        from stubo.cache.queue import get_redis_master
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
            'name=x&delay_type=fixed&milliseconds=7'), self.stop)
        self.wait()
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
                               'name=x&delay_type=fixed&milliseconds=8'),
                               self.stop)
        response = self.wait()
        delay_policy = Hash(get_redis_master()).get('localhost:delay_policy', 'x') 
        self.assertTrue(delay_policy['milliseconds'], 8)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"message": "Put Delay Policy Finished", 
                           u'status': 'updated', "delay_type": "fixed", 
                           "name": "x"}}
        payload = json.loads(response.body)
        self.assertEqual(payload, expect)   
                     

    def test_get_one_delay_policy(self):
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
                               'name=rtz_1&delay_type=fixed&milliseconds=700'),
                               self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url('/stubo/api/get/delay_policy?'
                                            'name=rtz_1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  'data': {'delay_type': 'fixed','milliseconds': '700',
                           'name': 'rtz_1'}}
        self.assertEqual(payload, expect)
        self.assertTrue(int(response.request_time) < 5)

    def test_get_many_delay_policies(self):
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
                               'name=rtz_1&delay_type=fixed&milliseconds=700'),
                               self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
            'name=rtz_2&delay_type=normalvariate&mean=100&stddev=50'), 
                               self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url('/stubo/api/get/delay_policy'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'),
                  "data": {"rtz_1": {"delay_type": "fixed", "name": "rtz_1",
                                     "milliseconds": "700"}, 
                  "rtz_2": {"delay_type": "normalvariate", "name": "rtz_2",
                            "stddev": "50", "mean": "100"}}}
        self.assertEqual(payload, expect)
        self.assertTrue(int(response.request_time) < 5)

class TestAcceptance(Base):  

    def test_exec_first_commands(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
                                            '/static/cmds/demo/first.commands'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubo_response = self.db.tracker.find_one({'function':'get/response'},
                             {'stubo_response':1})['stubo_response']
        self.assertEqual('Hello 2 World\n', stubo_response)
        cmds = ['delete/stubs?scenario=first',
                'begin/session?scenario=first&session=first_1&mode=record',
                'put/stub?session=first_1,first.textMatcher,first.response',
                'end/session?session=first_1',
                'begin/session?scenario=first&session=first_1&mode=playback',
                'get/response?session=first_1,first.request',
                'end/session?session=first_1']
        for cmd in cmds:
            self.assertTrue(cmd in response.body)

class TestRequestCacheLimit(Base):
    
    def test_cached_requests_are_in_limit(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
            '/static/cmds/tests/request_cache_limit/1.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        from stubo.cache.queue import Hash
        keys = Hash(self.redis_server).keys(
            'localhost:request_cache_limit:request')
        self.assertEqual(len(keys), self.cfg['request_cache_limit'])
        
    
class TestBigResponse(Base):  

    def test_exec_first_commands(self):
        '''Demonstrate handling of a 10mb response'''
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
                               '/static/cmds/tests/big/big.commands'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

class TestDelays(Base):

    def test_delay(self):
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
            'name=delay_1&delay_type=fixed&milliseconds=1000'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url(
                               '/stubo/api/get/response?session=first_1'),
                               callback=self.stop, method="POST",
                               body="get my stub")
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertTrue(float(response.request_time) > 0.999)

    def test_changing_delay(self):
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
            'name=delay_1&delay_type=fixed&milliseconds=500'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?'
            'name=delay_1&delay_type=fixed&milliseconds=70'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url(
                               '/stubo/api/get/response?session=first_1'),
                               callback=self.stop, method="POST",
                               body="get my stub")
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertTrue(float(response.request_time) > 0.069)
        
    def test_delete(self): 
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?name='
                               'delay_1&delay_type=fixed&milliseconds=500'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url(
                               '/stubo/api/delete/delay_policy?name=delay_1'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/get/delay_policy'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        self.assertEqual(payload['data'], {})
        
    def test_mulitiple_delete(self): 
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?name='
            'delay_1&delay_type=fixed&milliseconds=500'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?name='
            'delay_2&delay_type=fixed&milliseconds=500'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/delete/delay_policy'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/get/delay_policy'), self.stop)
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        self.assertEqual(payload['data'], {}) 
        
    def test_mulitiple_delete_by_name(self): 
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?name='
            'delay_1&delay_type=fixed&milliseconds=500'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/put/delay_policy?name='
            'delay_2&delay_type=fixed&milliseconds=500'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/delete/delay_policy?'
                               'name=delay_1&name=delay_2'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/get/delay_policy'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        self.assertEqual(payload['data'], {})             

class TestMatching(Base):

    def test_no_match_found(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
                               '/static/cmds/tests/accept/matcher1.commands'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        stubo_responses = self.db.tracker.find({'function':'get/response'})
        sr = []
        for resp in stubo_responses:
            sr.append(resp['stubo_response']) 
        self.assertEqual(2,len(sr))
        self.assertEqual('Hello from advanced matching.\n', sr[0])
        self.assertTrue('error' in sr[1])
        self.assertEqual('E017:No matching response found',
                         sr[1]['error']['message'])

class TestGeneralFunctionality(Base):

    def test_export(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
                               '/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url(
                               '/stubo/api/get/export?scenario=first'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        self.assertTrue('links' in payload['data'])
        self.assertEqual(1, len([x for x in payload['data']['links'] \
                                if x[0] == 'first.commands']))
        
        
        self.http_client.fetch(self.get_url(
                               '/stubo/api/delete/stubs?scenario=first'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        # load from the export
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
            '/static/exports/localhost_first/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
    def test_export_module(self):
        # load some stubs
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/ext/xslt/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        # export them
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/export?scenario=mangler_xslt'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        # delete
        self.http_client.fetch(self.get_url(
            '/stubo/api/delete/stubs?scenario=mangler_xslt'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        # load from the export
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/exports/localhost_mangler_xslt/mangler_xslt.commands'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)    

    def test_stub_count(self):
        # load some stubs
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        # count them
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/stubcount?scenario=first'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"count": 1, "scenario":"first", "host" : "localhost"}}
        self.assertEqual(payload, expect)
        
    def test_stub_count_with_host(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/stubcount?host=another'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"count": 0, "scenario": "all", "host" : "another"}}
        self.assertEqual(payload, expect)    

    def test_stub_count_all_scenarios(self):
        # load some stubs
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
                               '/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
                               '/static/cmds/tests/accept/matcher1.commands'),
                               self.stop)
        response = self.wait()

        # count them
        self.http_client.fetch(self.get_url('/stubo/api/get/stubcount'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"count": 2, "scenario": "all", "host" : "localhost"}}
        self.assertEqual(payload, expect)

    def test_get_status(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/status'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"cache_server": {"status": "ok", "local": True}, 
                  "info": {
                           "cluster": self.app.settings.get('cluster_name'),
                           "graphite_host" : self.app.settings.get('graphite.host'),
                  }, "database_server": {"status": "ok"}}}
        self.assertEqual(payload, expect)

    def test_get_scenario_status(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/accept/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url(
            '/stubo/api/get/status?scenario=first'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        
        expect = {"version": self.app.settings.get('stubo_version'), 
                  "data": {"cache_server": {"status": "ok", "local": True}, 
                  "info": {
                      "cluster": self.app.settings.get('cluster_name'),
                      "graphite_host" : self.app.settings.get('graphite.host'),
                  }, "database_server": {"status": "ok"}, 
                  "sessions": [[u'first_1', u'playback']]}}
        self.assertEqual(payload, expect)

    def test_get_session_status(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/accept/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url(
            '/stubo/api/get/status?session=first_1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        session = payload['data']['session']
        self.assertEqual(session['session'], 'first_1')
        self.assertEqual(session['status'], 'playback')
        self.assertEqual(session['scenario'], 'localhost:first')

    def test_get_version(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/version'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        expect = {"version": self.app.settings.get('stubo_version')}
        self.assertEqual(payload, expect)

class TestGetResponseWithHTTPHeaders(Base):
 
    def test_get_not_supported(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/response/foobar'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 405)

    def test_post_missing_stb_session(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/response/foobar'),
                               callback=self.stop,
            method="POST", body="hello")

        response = self.wait()
        self.assertEqual(response.code, 400)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        self.assertEqual("session not supplied in headers.",
                        payload['error']['message'])

    def test_post_fails_if_session_not_found(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/response/foobar'),
                               callback=self.stop, method="POST", body="hello",
                               headers={'ba_stb_session' : 'bar',
                                        'ba_stb_scenario' : 'foo'})
        response = self.wait()
        self.assertEqual(response.code, 400)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body)
        # shows its extracted the session from the header 
        self.assertEqual("session not found - localhost:foo_bar",
                        payload['error']['message'])

    def test_post_ok(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url('/stubo/api/get/response/foobar'), 
                               callback=self.stop,  method="POST",
                               body="get my stub", headers={
                               'ba_stb_scenario' : 'first',
                               'ba_stb_session' : '1'})
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertIn("Hello 2 World", response.body)
        
    def test_post_missing_stb_scenario(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url('/stubo/api/get/response/foobar'),
                               callback=self.stop, method="POST",
                               body="get my stub",
                               headers={'ba_stb_session' : 'first_1'})
        response = self.wait()
        self.assertEqual(response.code, 400)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        # shows its extracted the session from the header 
        self.assertEqual("scenario parameter not supplied in headers.",
                         payload['error']['message'])
        
    def test_url_param_takes_precedence(self):
        self.http_client.fetch(self.get_url(
                               '/stubo/api/get/response/foobar?session=pickme'), 
                               callback=self.stop,  method="POST",
                               body="get my stub", headers={
                               'ba_stb_scenario' : 'first',
                               'ba_stb_session' : '1'})
        response = self.wait()
        payload = json.loads(response.body)
        self.assertEqual("session not found - localhost:pickme",
                        payload['error']['message'])
    
class TestUseRequestInResponse(Base):

     def test_post_request_in_response_ok(self):
        '''Pick up the request text for use in the stubbed response'''
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/accept/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)       

        self.http_client.fetch(self.get_url(
                               '/stubo/api/get/response?session=first_1'),
                               callback=self.stop, method="POST",
                               body="<userid>abc123</userid>")
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertIn("Hello to abc123", response.body)

class TestEncoding(Base):

    def test_utf8_request(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
                               '/static/cmds/tests/encoding/1.commands'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)      
        stubo_response = self.db.tracker.find_one({'function':'get/response'},
            {'stubo_response':1})['stubo_response']
        self.assertEqual('hello', stubo_response)
        
    def test_utf8_in_all(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/encoding/utf8_in_all.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)      
        stubo_response = self.db.tracker.find_one({'function':'get/response'},
            {'stubo_response':1})['stubo_response']
        self.assertTrue(u'A*\xa3$' in stubo_response)                       

class TestPrivateVirtualStubo(Base):
    
    def get_url(self, path, host=None):
        host = host or 'localhost'
        """Returns an absolute url for the given path on the test server."""
        return '%s://%s:%s%s' % (self.get_protocol(), host,
                                self.get_http_port(), path)
   
    def test_virtual_host(self):
        # start a session 'first' in playback mode on localhost,
        # localhost get/status should  show the session
        # 127.0.0.1 get/status should not show the session
        # localhost get/response should works
        # 127.0.0.1 get/response should fail
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/accept/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(response.code, 200)       

        self.http_client.fetch(
          self.get_url('/stubo/api/get/status?session=first_1'), self.stop)                       
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(response.code, 200)  
        self.assertEqual(payload['data']['session'].get('status'), 'playback')     

        self.http_client.fetch(
          self.get_url('/stubo/api/get/status?session=first_1', 
                       host='127.0.0.1'), self.stop)
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(response.code, 200)       
        self.assertEqual(payload['data']['session'], {})
        

        self.http_client.fetch(self.get_url(
            '/stubo/api/get/response?session=first_1'), callback=self.stop,
            method="POST", body="get my stub")   
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertIn("Hello 2 World", response.body)

        self.http_client.fetch(
          self.get_url('/stubo/api/get/response?session=first_1', 
                       host='127.0.0.1'), callback=self.stop,
          method="POST", body="get my stub")
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        self.assertEqual(response.code, 400)
        payload = json.loads(response.body) 
        self.assertEqual(payload['error'].get('message'),
                         "session not found - 127.0.0.1:first_1")
        
    def test_mixedcase_host(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(response.code, 200)       

        self.http_client.fetch(
          self.get_url('/stubo/api/get/status?scenario=first',
                       host='LOcalhost'), self.stop)                       
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(response.code, 200)  
        self.assertEqual(payload['data']['sessions'][0], ["first_1", "dormant"])
        
        self.http_client.fetch(
          self.get_url('/stubo/api/begin/session?scenario=first&session=first_1&mode=playback',
                       host='LOcalhost'), self.stop)                       
        response = self.wait()
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(response.code, 200) 
        
        self.http_client.fetch(self.get_url('/stubo/api/get/response?session=first_1',  host='LOcalhost'), 
            self.stop, method='POST', body="get my stub")                 
        response = self.wait()
        self.assertEqual(response.code, 200)                


class TestState(Base):
    
    def test_state(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/state/converse.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubo_responses = self.db.tracker.find({'function':'get/response'})
        sr = []
        for resp in stubo_responses:
            sr.append(resp['stubo_response'])
        self.assertEqual(3,len(sr))
        self.assertTrue('PNR 12345 with standard meal' in sr[0])
        self.assertTrue('PNR 12345 has been updated (meal type change)' in sr[1])
        self.assertTrue('PNR 12345 with veggy meal' in sr[2])


    def test_state_reset(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/state/converse_reset.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubo_responses = self.db.tracker.find({'function':'get/response'})
        sr = []
        for resp in stubo_responses:
            sr.append(resp['stubo_response'])   
        self.assertEqual(4,len(sr))
        self.assertTrue('PNR 12345 with standard meal' in sr[0])
        self.assertTrue('PNR 12345 with standard meal' in sr[1])
        self.assertTrue('PNR 12345 has been updated (meal type change)' in sr[2])
        self.assertTrue('PNR 12345 with veggy meal' in sr[3])
    
    def test_state_loop(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/state/converse_loop.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubo_responses = self.db.tracker.find({'function':'get/response'})
        sr = []
        for resp in stubo_responses:
            sr.append(resp['stubo_response'])
        self.assertEqual(6,len(sr))
        self.assertTrue('PNR 12345 with standard meal' in sr[0])
        self.assertTrue('PNR 12345 has been updated (meal type change)' \
                        in sr[1])
        self.assertTrue('PNR 12345 with veggy meal' in sr[2])
        self.assertTrue('PNR 12345 with veggy meal' in sr[3])
        self.assertTrue('PNR 12345 has been updated (meal type change)' \
                        in sr[4])
        self.assertTrue('PNR 12345 with veggy meal' in sr[5])
    
    def test_multi_state(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/state/converse_multi.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubo_responses = self.db.tracker.find({'function':'get/response'})
        sr = []
        for resp in stubo_responses:
            sr.append(resp['stubo_response'])
        self.assertEqual(6,len(sr))
        self.assertTrue('PNR 12345 with standard meal' in sr[0])
        self.assertTrue('PNR 12345 has been updated (meal type change)' \
                        in sr[1])
        self.assertTrue('PNR 12345 with veggy meal' in sr[2])
        self.assertTrue('response d' in sr[3])
        self.assertTrue('response e' in sr[4])
        self.assertTrue('response f' in sr[5])

    def test_duplicate_stubs(self):
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url('/stubo/api/put/stub?session=first_1'), callback=self.stop,
        method="POST", body="||textMatcher||abcdef||response||a response")
        response = self.wait()
        self.assertEqual(response.code, 200)

        # insert a duplicate stub, which should not be loaded
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/stub?session=first_1'), callback=self.stop,
        method="POST", body="||textMatcher||abcdef||response||a response")
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubs = list(self.db.scenario_stub.find())
        self.assertTrue(len(stubs[0]['stub'].get('response')), 2)
        
    def test_ignore_duplicate_stubs(self):
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        self.http_client.fetch(self.get_url(
            '/stubo/api/put/stub?session=first_1&stateful=false'),
                               callback=self.stop,
        method="POST", body="||textMatcher||abcdef||response||a response")
        response = self.wait()
        self.assertEqual(response.code, 200)

        # insert a duplicate stub, which should not be loaded
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/stub?session=first_1&stateful=false'),
                               callback=self.stop,
        method="POST", body="||textMatcher||abcdef||response||a response")
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubs = list(self.db.scenario_stub.find())
        self.assertTrue(len(stubs[0]['stub'].get('response')), 1)  

class TestSmartCommands(Base):  

    def test_smart_commands(self):
        '''Demonstrate that command files can be Tornado templates with
           embedded code snippets. See the command file used in the next line.'''
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/accept/smart.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        stubo_response = self.db.tracker.find_one({'function':'get/response'},
            {'stubo_response':1})['stubo_response']
        self.assertEqual('Hello 2 World', stubo_response)

        cmds = ['delete/stubs?scenario=smart',
                'begin/session?scenario=smart&session=smart_1&mode=record',
                'put/stub?session=smart_1,first.textMatcher,first.response',
                'end/session?session=smart_1',
                'begin/session?scenario=smart&session=smart_1&mode=playback',
                'get/response?session=smart_1,first.request',
                'end/session?session=smart_1']
        for cmd in cmds:
            self.assertTrue(cmd in response.body)

        stubo_responses = self.db.tracker.find({'function':'get/response'})
        sr = []
        for resp in stubo_responses:
            sr.append(resp['stubo_response'])
        self.assertEqual(3,len(sr))
        self.assertTrue('Hello' in sr[0])
        self.assertTrue('Hello' in sr[1])
        self.assertTrue('Hello' in sr[2])
   
    def test_commands_with_foreign_urls(self):
        # Note that this only tests textMatcher and response files, not request files.
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
            '/static/cmds/tests/accept/foreign_url.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        found_bbc = False
        found_oracle = False
        found_matcher_text = False
        text_response = False
        from stubo.model.stub import Stub

        tracker_stubs = self.db.scenario_stub.find()
        for tracker_stub in tracker_stubs:
            stub = Stub(tracker_stub['stub'], 'xxx')
            matcher_text = stub.contains_matchers()[0]
            response_text = stub.response_body()[0]
            if '<!DOCTYPE html PUBLIC "-//W3C' in matcher_text:
                found_oracle = True
            if 'random_rubble' in matcher_text:
                found_matcher_text = True
            if "www.bbc.co.uk" in response_text:
                found_bbc = True
            if 'google' in response_text:
                found_google = True
            if 'response_text' in response_text:
                text_response = True
        self.assertTrue(found_oracle)
        self.assertTrue(found_matcher_text)
        self.assertTrue(text_response)
        self.assertTrue(found_bbc)

        found_text = False
        tracker_responses = self.db.tracker.find({'function':'get/response'})
        for response in tracker_responses:
            response_text = response['stubo_response']
            if 'response_text' in response_text:
                found_text = True
        self.assertTrue(found_text)

    def test_smart_commands_with_params(self):
        '''send arguments into a command file for its use.'''
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/accept/smart_arg.commands&scen=bob&session='
            'smart_1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        stubo_response = self.db.tracker.find_one({'function':'get/response'},
            {'stubo_response':1})['stubo_response']
        self.assertEqual('Hello 2 World', stubo_response)

class TestCommandsImport(Base):
    
    def _test_archive(self, archive):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=' 
            '/static/cmds/tests/exports/localhost_split/{0}'.format(archive)),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        cmds = [
            'put/module?name=/static/cmds/tests/ext/split/splitter.py',
            'delete/stubs?scenario=split&force=true',
            'begin/session?scenario=split&session=split_1&mode=record',
            'put/stub?session=split_1&ext_module=splitter&tracking_level=full,1.request,1.response',
            'end/session?session=split_1',
            'begin/session?scenario=split&session=split_1&mode=playback',
            'get/response?session=split_1&tracking_level=full,1.request',
            'end/session?session=split_1'             
        ]
            
        for cmd in cmds:
            self.assertTrue(cmd in response.body)   
          
    def test_tar_gzip(self):
        self._test_archive('split.tar.gz') 
            
    def test_zip(self):
        self._test_archive('split.zip') 
            
    def test_tar(self):
        self._test_archive('split.tar')
                                 
    def test_zip_from_export(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/export?scenario=first'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/exports/localhost_first/first.zip'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        cmds = ['delete/stubs?scenario=first',
                'begin/session?scenario=first&session=first_1&mode=record',
                'put/stub?session=first_1,first.textMatcher,first.response',
                'end/session?session=first_1']
        from urlparse import urlparse    
        for cmd in cmds:
            self.assertTrue(urlparse(cmd).path in response.body)  
            
    def test_tar_gzip_from_export(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/export?scenario=first'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/exports/localhost_first/first.tar.gz'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        cmds = ['delete/stubs?scenario=first',
                'begin/session?scenario=first&session=first_1&mode=record',
                'put/stub?session=first_1,first.textMatcher,first.response',
                'end/session?session=first_1']
        from urlparse import urlparse    
        for cmd in cmds:
            self.assertTrue(urlparse(cmd).path in response.body)   
            
    def test_post_exec_cmds(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/demo/first.commands'), callback=self.stop, 
                               method="POST", body="")
        response = self.wait()
        self.assertEqual(response.code, 200) 
                        
class TestSession(Base):
    
    def test_duplicate(self):
        from stubo.model.db import Scenario
        scenario = Scenario()
        scenario.insert(name='localhost:first', status='dormant')
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
                               'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 400)
        
    def test_end_session(self):
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/end/session?session='
            'first_1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(payload['data'], {"message": "Session ended"})
        
    def test_end_sessions(self):
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/end/sessions?scenario='
            'first'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(payload['data'], 
                         {u'first_1': {u'message': u'Session ended'}})  
        
    def test_end_sessions2(self):
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/stub?session=first_1'), callback=self.stop,
            method="POST", body="||textMatcher||abcdef||response||a response")
        response = self.wait()
        
        self.http_client.fetch(self.get_url(
                               '/stubo/api/end/session?session=first_1'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=playback'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_2&mode=playback'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/end/sessions?scenario='
            'first'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(payload['data'], 
                         {u'first_1': {u'message': u'Session ended'},
                          u'first_2': {u'message': u'Session ended'}})      
                  
        
    def test_warm_cache(self):     
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/stub?session=first_1'), callback=self.stop,
            method="POST", body="||textMatcher||abcdef||response||a response")
        response = self.wait()
        self.http_client.fetch(self.get_url(
            '/stubo/api/end/session?session=first_1'), callback=self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=playback&warm_cache=true'),
                               callback=self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        from stubo.cache import key_exists
        self.assertTrue(key_exists('localhost:first:request'))
        
    def test_stateful_warm_cache(self):     
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=record'), self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/stub?session=first_1'), callback=self.stop,
            method="POST", body="||textMatcher||abcdef||response||response1")
        response = self.wait()
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/stub?session=first_1'), callback=self.stop,
            method="POST", body="||textMatcher||abcdef||response||response2")
        response = self.wait()
        self.http_client.fetch(self.get_url(
            '/stubo/api/end/session?session=first_1'), callback=self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario='
            'first&session=first_1&mode=playback&warm_cache=true'),
                               callback=self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        from stubo.cache import key_exists
        self.assertTrue(key_exists('localhost:first:request')) 
        self.assertTrue(key_exists('localhost:first:request_index'))   
        
    def test_session_already_ended(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/end/session?scenario=first&session=first_1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Content-Type"], 
                         'application/json; charset=UTF-8')
        payload = json.loads(response.body) 
        self.assertEqual(response.code, 200)       
        self.assertEqual(payload['data']['message'], 'Session ended')
        
""" requires graphite stats server
class TestStats(Base):
    
    def test_recent(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/stats?cluster=aws_cluster1&from=-1mins'), self.stop)
        response = self.wait()
        self.assertTrue('application/json' in response.headers.get("Content-Type")) 
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'),
          {"metric": "latency", "percent_above_value": 50, 
           "target": "averageSeries(stats.timers.stubo.aws_cluster1.ba-perf-vip1.*.stuboapi.get_response.latency.mean_90)", 
           "pcent": 0.0,
           "from" : "-1mins",
           "to" : "now"})
        
    def test_higher_than_1sec(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/stats?cluster=aws_cluster1&from=-1mins&percent_above_value=1000'), self.stop)
        response = self.wait()
        self.assertTrue('application/json' in response.headers.get("Content-Type")) 
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'),
          {"metric": "latency", "percent_above_value": 1000, 
           "target": "averageSeries(stats.timers.stubo.aws_cluster1.ba-perf-vip1.*.stuboapi.get_response.latency.mean_90)", 
           "pcent": 0.0,
           "from" : "-1mins",
           "to" : "now"})
        
    def test_unknown_cluster(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/stats?cluster=bogus&from=-1mins&percent_above_value=1000'), self.stop)
        response = self.wait()
        self.assertTrue('application/json' in response.headers.get("Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload['error']['code'], 500)
        
    def test_bad_request(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/stats?cluster=aws_cluster1&from=xxxx'), self.stop)
        response = self.wait()
        self.assertTrue('application/json' in response.headers.get("Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload['error']['code'], 500)  
        
    def test_bad_arg(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/stats?cluster=aws_cluster1&from=-1mins&metric=bogus'), self.stop)
        response = self.wait()
        self.assertTrue('application/json' in response.headers["Content-Type"])
        payload = json.loads(response.body) 
        self.assertEqual(payload['error']['code'], 400) 
"""
        
class TestTracker(Base):  

    def test_response_size(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/delay_policy?name=foo'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/delay_policy'})
        self.assertEqual(int(response.headers['Content-Length']),
                         tracker['response_size'])
        
    def test_request_param(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/delay_policy?name=foo'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/delay_policy'})
        self.assertTrue('request_params' in tracker)
        self.assertEqual(tracker['request_params'].get('name'), 'foo') 
        
    def test_request_header(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/delay_policy?name=foo'), self.stop,
                               headers={'Foo' : 'bar'})
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/delay_policy'})
        self.assertTrue('request_headers' in tracker)  
        self.assertEqual(tracker['request_headers'].get('Foo'), 'bar')
        
    def test_request_param_multiple_values(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/delay_policy?name=foo&name=bar'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/delay_policy'})
        self.assertTrue('request_params' in tracker)
        self.assertEqual(tracker['request_params'].get('name'), ['foo', 'bar']) 
        
    def test_request_param_multiple_values2(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/delay_policy?name=foo&another_key=bar'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/delay_policy'})
        self.assertTrue('request_params' in tracker)
        self.assertEqual(tracker['request_params'].get('name'), 'foo') 
        self.assertEqual(tracker['request_params'].get('another_key'), 'bar')
        
    def test_request_param_skip_dotted_name(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/delay_policy?name=foo&bar.1=xxx'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/delay_policy'})
        self.assertTrue('request_params' in tracker)
        self.assertEqual(tracker['request_params'].get('bar.1'), None) 
        self.assertEqual(tracker['request_params'].get('name'), 'foo') 
        
    def test_request_param_skip_dotted_name_in_headers(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/delay_policy?name=foo&bar.1=xxx'), self.stop,
                               headers={'bar.1' : 'hello'})
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/delay_policy'})
        self.assertTrue('request_params' in tracker)
        self.assertEqual(tracker['request_params'].get('bar.1'), None) 
        self.assertEqual(tracker['request_params'].get('name'), 'foo') 
        
    def test_request_session_param_in_headers(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
            '/static/cmds/tests/accept/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        self.http_client.fetch(self.get_url('/stubo/api/get/response'), 
            self.stop, method='POST', body="get my stub", 
            headers={'Stubo-Request-Session' : 'first_1'})                 
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/response'})
        self.assertEqual(tracker['request_headers'].get(
            'Stubo-Request-Session'), 'first_1') 
        
    def test_request_session_legacy_param_in_headers(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
            '/static/cmds/tests/accept/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        self.http_client.fetch(self.get_url('/stubo/api/get/response'), 
            self.stop, method='POST', body="get my stub", 
            headers={'stb_session' : '1', 'stb_scenario' : 'first'})                 
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'get/response'})
        self.assertEqual(tracker['request_headers'].get(
            'Stubo-Request-Session'), 'first_1')     
                    
    def test_stubo_response_is_trimmed(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/exec/cmds?cmdFile=/static/cmds/demo/first.commands'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        tracker = self.db.tracker.find_one({'function':'exec/cmds'})
        self.assertEqual(int(response.headers['Content-Length']), tracker['response_size']) 
        self.assertTrue(int(response.headers['Content-Length']) > len(tracker['stubo_response']))         
        
    def test_minimal_tracking_level(self):
        '''Show minimal tracking data for a get/response'''
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
            '/static/cmds/tests/accept/minimal_logging.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        tracker = self.db.tracker.find_one({'function':'get/response'})
        # minimal or full tracking level items
        self.assertEqual(tracker['function'], "get/response")
        self.assertTrue(tracker['start_time'] != None)
        self.assertEqual(tracker['return_code'], 200)
        self.assertTrue(tracker['server'] != None)
        self.assertTrue(tracker['host'] != None)
        self.assertEqual(tracker['request_params']['session'], "first_1")
        self.assertEqual(tracker['scenario'], "first")
        self.assertTrue(tracker['duration_ms'] != None)
        self.assertTrue(tracker['remote_ip'] != None)
        self.assertTrue(tracker['delay'] != None)
        self.assertEqual(tracker['stubo_response'], "Hello 2 World")

        # not for minimal tracking as these can be big.
        self.assertFalse(tracker.has_key('request_text'))
        self.assertFalse(tracker.has_key('matchers'))
        self.assertFalse(tracker.has_key('raw_response'))
        self.assertFalse(tracker.has_key('encoded_response'))

    def test_full_tracking_level(self):
        '''Show full debug level tracking for a get/response call(tracking_level=full)'''
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdFile='
            '/static/cmds/tests/accept/full_logging.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        tracker = self.db.tracker.find_one({'function':'get/response'})
        # minimal or full tracking level items
        self.assertEqual(tracker['function'], "get/response")
        self.assertTrue(tracker['start_time'] != None)
        self.assertEqual(tracker['return_code'], 200)
        self.assertTrue(tracker['server'] != None)
        self.assertTrue(tracker['host'] != None)
        self.assertEqual(tracker['request_params']['session'], "first_1")
        self.assertEqual(tracker['scenario'], "first")
        self.assertTrue(tracker['duration_ms'] != None)
        self.assertTrue(tracker['remote_ip'] != None)
        self.assertTrue(tracker['delay'] != None)
        self.assertIn("Hello 2 World this is", tracker['stubo_response'])

        # full tracking only 
        self.assertEqual(tracker.get('tracking_level'), "full")
        self.assertEqual(tracker['request_text'],
                         'timestamp: 09:23:45\nget my stubs\n')
        self.assertTrue('trace' in tracker)
            
class TestSetting(Base):  

    def test_set(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=foo&value=bar'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "new": "true", "host": "localhost", "all" : False, "foo": "bar"
        }) 
        
    def test_modify(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=foo&value=bar'), self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=foo&value=bar2'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.assertTrue('application/json' in response.headers.get("Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "new": "false", "host": "localhost", "all" : False, "foo": "bar2"
        })   
        
    def test_get(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=foo&value=bar'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/setting?setting=foo'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)  
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "host": "localhost", "all" : False, "foo": "bar"
        })  
        
    def test_get_all(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=foo&value=bar'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=foo2&value=bar2'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/setting?'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)  
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "host": "localhost", "all" : False, 
            "settings" : {"foo": "bar", "foo2": "bar2"}
        })      
        
    def test_empty_get(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/setting?setting=foo'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)  
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "host": "localhost", "all" : False, "foo": None
        })  
        
    def test_global_set(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?host=all&setting=foo&value=bar'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "new": "true", "host": "localhost", "all" : True, "foo": "bar"
        }) 
        
    def test_global_modify(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?host=all&setting=foo&value=bar'), self.stop)
        response = self.wait()
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?host=all&setting=foo&value=bar2'),
                               self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "new": "false", "host": "localhost", "all" : True, "foo": "bar2"
        })   
        
    def test_global_get(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?host=all&setting=foo&value=bar'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/setting?host=all&setting=foo'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)  
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "host": "localhost", "all" : True, "foo": "bar"
        })  
        
    def test_global_empty_get(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/get/setting?host=all&setting=foo'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)  
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('data'), {
            "host": "localhost", "all" : True, "foo": None
        }) 
        
    
    def test_blacklisted(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=blacklisted&value=true'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.http_client.fetch(self.get_url(
            '/stubo/api/begin/session?scenario=foo&session=foo_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 400)   
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('error'), {
            'code': 400,                                    
            'message': "Sorry the host URL 'localhost' has been blacklisted. Please contact Stub-O-Matic support."
        }) 
        
    def test_blacklisted2(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=blacklisted&value=1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.http_client.fetch(self.get_url(
            '/stubo/api/begin/session?scenario=foo&session=foo_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 400)   
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('error'), {
            'code': 400,                                    
            'message': "Sorry the host URL 'localhost' has been blacklisted. Please contact Stub-O-Matic support."
        })   
        
    def test_blacklisted3(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=blacklisted&value=True'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.http_client.fetch(self.get_url(
            '/stubo/api/begin/session?scenario=foo&session=foo_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 400)   
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('error'), {
            'code': 400,                                    
            'message': "Sorry the host URL 'localhost' has been blacklisted. Please contact Stub-O-Matic support."
        })          
        
    def test_blacklisted_off(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=blacklisted&value=true'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.http_client.fetch(self.get_url(
            '/stubo/api/begin/session?scenario=foo&session=foo_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 400)   
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('error'), {
            'code': 400,                                    
            'message': "Sorry the host URL 'localhost' has been blacklisted. Please contact Stub-O-Matic support."
        }) 
        
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=blacklisted&value=false'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.http_client.fetch(self.get_url(
            '/stubo/api/begin/session?scenario=foo&session=foo_1&mode=record'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)      
        
    def test_blacklisted_on_get_response(self):
        self.http_client.fetch(self.get_url(
            '/stubo/api/put/setting?setting=blacklisted&value=true'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)              
        self.http_client.fetch(self.get_url(
                               '/stubo/api/get/response?session=foo'),
                               callback=self.stop, method="POST",
                               body="get my stub")
        response = self.wait()
        self.assertEqual(response.code, 400)   
        self.assertTrue('application/json' in response.headers.get(
                        "Content-Type"))
        payload = json.loads(response.body) 
        self.assertEqual(payload.get('error'), {
            'code': 400,                                    
            'message': "Sorry the host URL 'localhost' has been blacklisted. Please contact Stub-O-Matic support."
        })                               
             
class TestTemplates(Base):  

    def test_matcher(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/templates/matcher/all.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        result = list(self.db.tracker.find({'function':'get/response'}))
        self.assertEqual(1, len(result))
        response = result[0]['stubo_response']
        self.assertEqual(response, '<response>you found me</response>')
      
        
    def test_dateroll_args(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/templates/dateroll/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)

        result = list(self.db.tracker.find({'function':'get/response'}))
        self.assertEqual(1, len(result))
        response = result[0]['stubo_response']
        import datetime
        d = datetime.date.today()
        self.assertTrue('<putstub_arg>this stub was recorded at {0}'.format(
                        d) in response)
        self.assertTrue('<getresponse_arg>this stub was played at {0}'.format(
                        d) in response)
        
        
       
class TestGetScenarios(Base):       
    
    def test_empty(self):
        self.http_client.fetch(self.get_url('/stubo/api/get/scenarios'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload.get('data'), 
                         {"scenarios": [], "host": "localhost"})
        
    def test_host(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        self.http_client.fetch(self.get_url('/stubo/api/get/scenarios'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload.get('data'), 
                         {"scenarios": ["localhost:first"], "host": "localhost"}) 
        
        self.http_client.fetch(self.get_url('/stubo/api/get/scenarios?host=localhost'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload.get('data'), 
                         {"scenarios": ["localhost:first"], "host": "localhost"}) 
        
    def test_all_hosts(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile='
            '/static/cmds/tests/state/converse.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        self.http_client.fetch(self.get_url('/stubo/api/get/scenarios'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload.get('data'), 
            {"scenarios": ["localhost:first", "localhost:converse"], 
             "host": "localhost"})       
        
    def test_other_host(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        self.http_client.fetch(self.get_url('/stubo/api/get/scenarios?host=bogus'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload.get('data'), 
                         {"scenarios": [], "host": "bogus"}) 
        
             
class TestGetResponse(Base):
    
    def test_mode_in_playback(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/end/session?session=first_1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        
        self.http_client.fetch(self.get_url('/stubo/api/get/response?session=first_1'), self.stop,
                                method="POST", body="timestamp: 09:23:45 get my stub")
        response = self.wait()
        self.assertEqual(response.code, 500) 
        payload = json.loads(response.body)    
        self.assertTrue(payload['error']['message'].startswith("cache status != playback"))
        
    def test_get_response_url_session_arg_is_used(self):
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.http_client.fetch(self.get_url('/stubo/api/end/session?session=first_1'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        
        self.http_client.fetch(self.get_url('/stubo/api/begin/session?scenario=first&session=playme&mode=playback'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200) 
        
        self.http_client.fetch(self.get_url('/stubo/api/get/response?session=playme'), self.stop,
                                method="POST", body="timestamp: 09:23:45 get my stub")
        response = self.wait()
        self.assertEqual(response.code, 200) 
        
        tracker = self.db.tracker.find_one({'function':'get/response'})
        self.assertEqual(tracker['request_params'].get('session'), 'playme')
                  
class TestHTTPCompression(Base):    
     
    def get_httpserver_options(self):
        return dict(decompress_request=True)   
   
    def test_gzip_request(self):  
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        import StringIO, gzip
        stringio = StringIO.StringIO()
        gzip_file = gzip.GzipFile(fileobj=stringio, mode='w')
        gzip_file.write("get my stub")
        gzip_file.close()
     
        response =  self.http_client.fetch(self.get_url('/stubo/api/get/response?session=first_1'),  
                                           self.stop, 
                                           use_gzip=False,
                                           headers={"Content-Encoding": "gzip",
                                                    "Accept-Encoding": "gzip"},
                                           method="POST", 
                                           body=stringio.getvalue())
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body[:-1], b"Hello 2 World")   
        
    def test_gzip_response_is_disabled(self):
         
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        
        response =  self.http_client.fetch(self.get_url('/stubo/api/get/response?session=first_1'),  self.stop, 
                                           use_gzip=False,
                                           headers={"Accept-Encoding": "gzip"},
                                           method="POST", body="get my stub")
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertNotEqual(response.headers.get("Content-Encoding"), "gzip")
        self.assertEqual(response.body[:-1], b"Hello 2 World")     
      
class TestHTTPResponseCompressionEnabled(Base):
        
    def get_app(self):    
          self.cfg['compress_response'] = True
          return super(TestHTTPResponseCompressionEnabled, self).get_app()
                
    def test_gzip_response(self):
         
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
        response =  self.http_client.fetch(self.get_url('/stubo/api/get/response?session=first_1'),  self.stop, 
                                           use_gzip=False,
                                           headers={"Accept-Encoding": "gzip"},
                                           method="POST", body="get my stub")
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers.get("Content-Encoding"), "gzip")
        # Our test data gets bigger when gzipped.  Oops.  :)
        self.assertEqual(len(response.body), 34)
        import gzip
        f = gzip.GzipFile(mode="r", fileobj=response.buffer)
        self.assertEqual(f.read()[:-1], b"Hello 2 World")
        
    def test_gzip_response_not_desired(self):
         
        self.http_client.fetch(self.get_url('/stubo/api/exec/cmds?cmdfile=/static/cmds/demo/first_setup.commands'), self.stop)
        response = self.wait()
        self.assertEqual(response.code, 200)
         
        response =  self.http_client.fetch(self.get_url('/stubo/api/get/response?session=first_1'),  self.stop, 
                                           use_gzip=False,
                                           headers={"Accept-Encoding": "identity"},
                                           method="POST", body="get my stub")
        response = self.wait()
        self.assertEqual(response.code, 200)
        self.assertNotEqual(response.headers.get("Content-Encoding"), "gzip")
        self.assertEqual(response.body[:-1], b"Hello 2 World")    
       
        
