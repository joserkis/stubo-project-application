"""  
    :copyright: (c) 2015 by OpenCredo.
    :license: GPLv3, see LICENSE for more details.
"""
import os
import zipfile
import tarfile
import shutil
import logging
import random
import time
import sys
import copy
import json
from urlparse import urlparse
from StringIO import StringIO
from contextlib import closing
import codecs

from tornado.web import MissingArgumentError

from stubo.model.db import (
    Scenario, get_mongo_client, session_last_used
)    
import stubo.model.db
from stubo.model.cmds import (
    StuboCommandFile, UriLocation, UrlFetch, form_input_cmds
)
from stubo.model.stub import Stub, StubCache, parse_stub
from stubo.exceptions import (
    exception_response, StuboException, UserExitModuleNotFound
)
from stubo import version
from stubo.cache import (
    Cache, add_request, compute_hash, get_redis_server, get_keys
)  

from stubo.utils import (
    asbool, make_temp_dir, get_export_links, get_hostname,
    human_size, pretty_format_python, as_date, compact_traceback
)
from stubo.utils.track import TrackTrace
from stubo.match import match
from stubo.model.request import StuboRequest
from stubo.ext import today_str
from stubo.ext.transformer import transform
from stubo.ext.module import Module
from stubo.testing import DummyModel

    
log = logging.getLogger(__name__)

def get_dbenv(handler):
    dbenv = None
    if 'mongo.host' in handler.settings:
        dbenv = stubo.model.db.default_env.copy()
        dbenv.update({
            'host' : handler.settings['mongo.host'],
            'port' : int(handler.settings['mongo.port'])
            })
    return dbenv    
    
def export_stubs(handler, scenario_name):
    cache = Cache(get_hostname(handler.request))  
    scenario_name_key = cache.scenario_key_name(scenario_name)
    scenario = Scenario()
    stubs = list(scenario.get_stubs(scenario_name_key))
    """
    [{   u'_id': ObjectId('537c8f1cac5f7303ad704d85'),
    u'scenario': u'localhost:first',
    u'stub': {   u'recorded': u'2014-05-21',
                 u'request': {   u'bodyPatterns': [   {   u'contains': [   u'get my stub\n']}],
                                 u'method': u'POST'},
                 u'response': {   u'body': u'Hello {{1+1}} World\n',
                                  u'delayPolicy': u'slow',
                                  u'status': 200}}}]
    """
    # use user arg or epoch time
    session_id = handler.get_argument('session_id', int(time.time()))  
    session = u'{0}_{1}'.format(scenario_name, session_id) 
    cmds = [
        'delete/stubs?scenario={0}'.format(scenario_name),
        'begin/session?scenario={0}&session={1}&mode=record'.format(
         scenario_name, session)
    ]
    files = []
    if len(stubs) > 0:
        for i in range(len(stubs)):
            entry = stubs[i]
            stub = Stub(entry['stub'], scenario_name_key)
            matchers = [('{0}_{1}_{2}.textMatcher'.format(session, i, x), 
                stub.contains_matchers()[x]) for x in range(len(
                stub.contains_matchers()))]
            matchers_str = ",".join(x[0] for x in matchers)
            url_args = 'session={0}'.format(session)
            module_info = stub.module()
            if module_info:
                # Note: not including put/module in the export, modules are shared
                # by multiple scenarios.
                url_args += '&ext_module={0}&stub_created_date={1}&stubbedSystem'\
                    'Date={2}&system_date={3}'.format(module_info['name'], 
                    stub.recorded(), module_info.get('recorded_system_date'),
                    module_info.get('system_date'))
            responses = stub.response_body()        
            for ii in range(len(responses)):
                response = responses[ii]
                response = ('{0}_{1}.response.{2}'.format(session, i, ii), 
                            responses[ii]) 
                cmds.append('put/stub?{0},{1},{2}'.format(url_args, matchers_str,
                                                          response[0]))
                files.append(response)    
            files.extend(matchers)
    else:
        cmds.append('put/stub?session={0},text=a_dummy_matcher,text=a_dummy_response'.format(session))
       
    cmds.append('end/session?session={0}'.format(session))
    bookmarks = cache.get_all_saved_request_index_data() 
    if bookmarks:
        cmds.append('import/bookmarks?location=bookmarks')
        files.append(('bookmarks', json.dumps(bookmarks)))  
    
    files.append(('{0}.commands'.format(scenario_name),
                  b"\r\n".join(cmds)))

    static_dir = handler.settings['static_path']
    scenario_dir = os.path.join(static_dir, 'exports', 
                                scenario_name_key.replace(':', '_'))

    if os.path.exists(scenario_dir):
        shutil.rmtree(scenario_dir)
    os.makedirs(scenario_dir)

    archive_name = os.path.join(scenario_dir, scenario_name)
    zout = zipfile.ZipFile(archive_name+'.zip', "w")
    tar = tarfile.open(archive_name+".tar.gz", "w:gz")
    for finfo in files:
        fname, contents = finfo
        file_path = os.path.join(scenario_dir, fname)
        with codecs.open(file_path, mode='wb', encoding='utf-8') as f:
            f.write(contents)
        tar.add(file_path, fname)
        zout.write(file_path, fname)
    tar.close()     
    zout.close() 
    shutil.copy(archive_name+'.zip', archive_name+'.jar')  

    files.extend([(scenario_name+'.zip',), (scenario_name+'.tar.gz',),
                  (scenario_name+'.jar',)])
    links = get_export_links(handler, scenario_name_key, files)
    payload = dict(scenario=scenario_name, scenario_dir=scenario_dir,
                   links=links)
    return dict(version=version, data=payload)

def list_stubs(handler, scenario_name, host=None):
    cache = Cache(host or get_hostname(handler.request))
    scenario = Scenario()
    stubs = scenario.get_stubs(cache.scenario_key_name(scenario_name))
    result = dict(version=version, data=dict(scenario=scenario_name))
    if stubs:
        result['data']['stubs'] = [x['stub'] for x in stubs]
    return result

def list_scenarios(host):
    response = {'version' : version}
    scenario_db = Scenario()
    if host == 'all':
        scenarios = [x['name'] for x in scenario_db.get_all()]
    else:
        # get all scenarios for host
        scenarios = [x['name'] for x in scenario_db.get_all(
                                            {'$regex': '{0}:.*'.format(host)})]
    response['data'] = dict(host=host, scenarios=scenarios)    
    return response        
    
def stub_count(host, scenario_name=None):
    if host == 'all':
        scenario_name_key = None
    else:    
        if not scenario_name:
            # get all stubs for this host
            value = '{0}:.*'.format(host)
            scenario_name_key = {'$regex': value}   
        else: 
            scenario_name_key = ":".join([host, scenario_name])   
    scenario = Scenario()
    result = {'version' : version}
    count = scenario.stub_count(scenario_name_key)
    result['data'] = {'count' : count, 
                      'scenario' : scenario_name or 'all',
                      'host' : host}
    return result    

def get_stubs(host, scenario_name=None):
    if not scenario_name:
        # get all stubs for this host
        scenario_name_key = {'$regex': '{0}:.*'.format(host)}   
    else: 
        scenario_name_key = ":".join([host, scenario_name])   
    scenario = Scenario()
    return scenario.get_stubs(scenario_name_key)

def run_command_file(cmd_file_url, request, static_path):   
    def run(cmd_file_path):
        response = {
            'version' : version
        }
        cmd_processor = StuboCommandFile(request, cmd_file_path)
        cmds = cmd_processor.run()
        cmd_links = [(x, '') for x in cmds]
        response['data'] = {'executed_commands' : cmd_links}
        return response
    file_type = os.path.basename(urlparse(cmd_file_url).path).rpartition(
                                '.')[-1]  
    supported_types = ('zip', 'gz', 'tar', 'jar')  
    if file_type in supported_types:
        # import compressed contents and run contained .commands file
        import_dir = os.path.join(static_path, 'imports')
        with make_temp_dir(dirname=import_dir) as temp_dir: 
            temp_dir_name = os.path.basename(temp_dir)
            response, headers = UrlFetch().get(UriLocation(request)(
                                               cmd_file_url)[0])
            content_type = headers["Content-Type"]
            log.debug('received {0} file.'.format(content_type))
            if content_type == 'application/x-tar' or file_type == 'tar':
                with closing(tarfile.open(fileobj=StringIO(response))) as tar:
                    tar.extractall(path=temp_dir)
                    # find the commands file in the extract
                    cmds = [x for x in tar.getnames() if x.endswith(
                        '.commands')]
                    if not cmds:
                        raise exception_response(400, title='.commands file not'
                            ' found in tar: {0}'.format(cmd_file_url))            
                    response = run(os.path.join('static', 'imports', 
                                                temp_dir_name, cmds[0]))
               
            elif content_type in ('application/zip',
                                  'application/java-archive') or file_type in \
                                  ('zip', 'jar'):
                with zipfile.ZipFile(StringIO(response)) as zipf:
                    zipf.extractall(path=temp_dir)
                    # find the commands file in the extract
                    cmds = [x for x in zipf.namelist() if x.endswith(
                        '.commands')]
                    if not cmds:
                        raise exception_response(400, title='.commands file not'
                            ' found in zip: {0}'.format(cmd_file_url))       
                    response = run(os.path.join('static', 'imports', 
                                                temp_dir_name, cmds[0]))
            else:
                raise exception_response(400, title='Expected Content-Type has'
                    ' to be one of these: {0} not {1}'.format(supported_types,
                                                              content_type))
    else:
        response = run(cmd_file_url)
    return response
    
def run_commands(handler, cmds_text):
    response = {
        'version' : version
    }
    host = get_hostname(handler.request)
    def get_links(cmd):
        cmd_uri = urlparse(cmd)
        links = []
        if cmd_uri.path == 'get/export':
            scenario_name = cmd_uri.query.partition('=')[-1]
            scenario_name_key = '{0}:{1}'.format(host, scenario_name)
            files = [(scenario_name+'.zip',), (scenario_name+'.tar.gz',),
                     (scenario_name+'.jar',)]
            links = get_export_links(handler, scenario_name_key, files)
        return links
    cmd_processor = StuboCommandFile(handler.request)
    cmds = cmd_processor.parse_commands(cmds_text)
    cmd_pairs = [(x, get_links(x)) for x in cmds if urlparse(
        x).path in form_input_cmds]
    if not cmd_pairs:
        raise exception_response(400, title='command/s not supported, must be '
            'one of these: {0}'.format(form_input_cmds))
        
    cmds, _ = zip(*cmd_pairs)
    cmd_processor.run_cmds(cmds)              
    response['data'] = {'executed_commands' : cmd_pairs}
    return response

def delete_module(request, names):
    module = Module(get_hostname(request))
    removed = []  
    for name in names:
        loaded_versions = [x for x in sys.modules.keys() if \
                              '{0}_v'.format(name) in x]
        for loaded in loaded_versions:
            module.remove_sys_module(loaded)
        if module.remove(name):
            removed.append('{0}:{1}'.format(module.host(), name))
    return {
        'version' : version,
        'data' : {'message' : 'delete modules: {0}'.format(names),
                  'deleted' : removed}
    } 
           
def list_module(handler, names):
    module = Module(get_hostname(handler.request))
    info = {}
    if not names:
        names = [x.rpartition(':')[-1] for x in get_keys(
            '{0}:modules:*'.format(module.host()))]
    for name in names:
        loaded_sys_versions = [x for x in sys.modules.keys() if \
                              '{0}_v'.format(name) in x]
        lastest_code_version = module.latest_version(name)
        info[name] = {       
            'latest_code_version' : lastest_code_version,
            'loaded_sys_versions' :  loaded_sys_versions
        }
    payload = dict(message='list modules', info=info)  
    return {
        'version' : version,
        'data' : payload
    }            
            
def put_module(handler, names):
    module = Module(handler.track.host)
    added = []
    result = dict(version=version)
    for name in names:
        uri, module_name = UriLocation(handler.request)(name)
        log.info('uri={0}, module_name={1}'.format(uri, module_name))
        response, _ = UrlFetch().get(uri)
        module_name = module_name[:-3]
        last_version = module.latest_version(module_name)
        module_version_name = module.sys_module_name(module_name, 
                                                     last_version+1) 
        if last_version and response == module.get_source(module_name,
                                                          last_version):
            msg = 'Module source has not changed for {0}'.format(
                                                        module_version_name)
            result['data'] = dict(message=msg)
        try:  
            code, mod = module.add_sys_module(module_version_name, response)
            log.debug('{0}, {1}'.format(mod, code))
        except Exception, e:
            _, t, v, tbinfo = compact_traceback()
            msg = u'error={0}'.format(e)
            stack_trace = u'traceback is: ({0}: {1} {2})'.format(t, v, tbinfo)
            log.error(msg) 
            raise exception_response(400,
                title='Unable to compile {0}:{1}, {2}'.format(module.host(), 
                module_version_name, msg), traceback=stack_trace)
        module.add(module_name, response)
        added.append(module_version_name)
    result['data'] = dict(message='added modules: {0}'.format(added))
    return result

def put_stub(handler, session_name, delay_policy, stateful,
             recorded=None, module_name=None, recorded_module_system_date=None): 
    log.debug('put_stub request: {0}'.format(handler.request))
    request = handler.request
    stubo_request = StuboRequest(request)
    session_name = session_name.partition(',')[0]
    cache = Cache(get_hostname(request))
    scenario_key = cache.find_scenario_key(session_name)
    trace = TrackTrace(handler.track, 'put_stub')
    url_args = handler.track.request_params
    try:
        is_json = 'application/json' in request.headers.get('Content-Type', {})
        stub = parse_stub(stubo_request.body_unicode, scenario_key, url_args,
                          is_json)
    except Exception, e:    
        raise exception_response(400, title='put/stub body format error - {0}, '
            'on session: {1}'.format(e.message, session_name))
                                                   
    log.debug('stub: {0}'.format(stub))
    if delay_policy:
        stub.set_delay_policy(delay_policy)
       
    session = cache.get_session(scenario_key.partition(':')[-1], 
                                session_name, 
                                local=False)
    if not session:
        raise exception_response(400, title='session not found - {0}'.format(
                                 session_name))       
    stub.set_recorded(recorded or today_str('%Y-%m-%d'))   
    if module_name:
        stub.set_module({
            'name' : module_name, 
             # TODO: is module['system_date'] used?
            'system_date' : today_str('%Y-%m-%d'),
            'recorded_system_date' : recorded_module_system_date or today_str(
                '%Y-%m-%d')
        })  
        trace.info('module used', stub.module()) 
        try:
            source_stub = copy.deepcopy(stub)
            stub, _ = transform(stub, stubo_request, function='put/stub', 
                                cache=handler.settings['ext_cache'],
                                hooks=handler.settings['hooks'],
                                stage='put/stub',
                                trace=trace,
                                url_args=url_args)
            if source_stub != stub:
                trace.diff('stub was transformed', source_stub.payload, 
                           stub.payload)
                trace.info('stub was transformed into', stub.payload)
        except UserExitModuleNotFound, e:
            # ignore legacy stubbedSystem param
            stub.payload.pop('module')   
                                                                     
    scenario_name = session['scenario'] 
    handler.track.scenario = scenario_name.partition(':')[2]
    session_status = session['status']
    if session_status != 'record':
        raise exception_response(400, title='Scenario not in record '
            'mode - {0} in {1} mode.'.format(scenario_name, session_status))
    doc = dict(scenario=scenario_name, stub=stub)
    scenario_col = Scenario()
    result = scenario_col.insert_stub(doc, stateful)
    response = {
        'version' : version
    } 
    response['data'] = {'message' : result}
    return response

def calculate_delay(policy):
    delay = 0
    delay_type = policy.get('delay_type')
    if delay_type == 'fixed':
        delay = policy['milliseconds']
    elif delay_type == 'normalvariate':
        # Calculate from the normal distribution, but set minimum at zero
        delay = max(0.0, random.normalvariate(int(policy['mean']),
                                              int(policy['stddev'])))
    else:
        log.warn('unknown delay type: {0} encountered'.format(delay_type))
    return float(delay)
                             
def get_response(handler, session_name):
    request = handler.request
    stubo_request = StuboRequest(request)
    request_body = stubo_request.request_body()
    if not request_body:
        # TODO: not an error if they match on other attrs
        raise exception_response(400, title='No text in body')
    cache = Cache(get_hostname(request))
    if cache.blacklisted():
        raise exception_response(400, title="Sorry the host URL '{0}' has been "
         "blacklisted. Please contact Stub-O-Matic support.".format(cache.host))
    scenario_key = cache.find_scenario_key(session_name)  
    scenario_name = scenario_key.partition(':')[-1] 
    handler.track.scenario = scenario_name   
    request_id = compute_hash(request_body)
    module_system_date = handler.get_argument('system_date', None)
    url_args = handler.track.request_params
    if not module_system_date:
        # BA LEGACY
        module_system_date = handler.get_argument('stubbedSystemDate', None)
    trace_matcher = TrackTrace(handler.track, 'matcher')
    user_cache = handler.settings['ext_cache']
    # check cached requests
    cached_request = cache.get_request(scenario_name, session_name, request_id)
    if cached_request:
        response_ids, delay_policy_name, recorded, system_date, module_info, request_index_key = cached_request
    else: 
        retry_count = 5 if handler.settings.get('is_cluster', False) else 1 
        session, retries = cache.get_session_with_delay(scenario_name, 
                                                        session_name,
                                                        retry_count=retry_count,
                                                        retry_interval=1)
        if retries > 0:
            log.warn("replication was slow for session: {0} {1}, it took {2} "\
              "secs!".format(scenario_key, session_name, retries+1))
        if session['status'] != 'playback':
            raise exception_response(500, 
                title='cache status != playback. session={0}'.format(session))
            
        system_date = session['system_date'] 
        if not system_date:
            raise exception_response(500,
                title="slave session {0} not available for scenario {1}".format(
                session_name, scenario_key))          
                
        session['ext_cache'] = user_cache   
        results = match(stubo_request, session, trace_matcher, 
                        as_date(system_date), 
                        url_args=url_args,
                        hooks=handler.settings['hooks'],
                        module_system_date=module_system_date)
        # 0 is best match
        hits_info, stub = results[0]
        log.debug(u'match result: (hits_info={0}, stub={1})'.format(hits_info, 
                  stub.payload)) 
        hits, stub_number = hits_info
        if not hits:
            raise exception_response(400, 
                                     title='E017:No matching response found')
        response_ids = stub.response_ids()
        delay_policy_name = stub.delay_policy_name() 
        recorded = stub.recorded()
        module_info = stub.module()    
        request_index_key = add_request(session, request_id, stub, system_date,
                                        stub_number,
                                        handler.settings['request_cache_limit'])
        if not stub.response_body():
            stub.set_response_body(stub.get_response_body_from_cache(
                                   request_index_key))
        if delay_policy_name:    
            stub.load_delay_from_cache(delay_policy_name)     
        
    if cached_request:
        stub = StubCache({}, scenario_key, session_name)
        stub.load_from_cache(response_ids, delay_policy_name, recorded, 
                             system_date, module_info, request_index_key)   
    trace_response = TrackTrace(handler.track, 'response')
    if module_info:
        trace_response.info('module used', str(module_info))        
    response_text = stub.response_body()
    if not response_text:
        raise exception_response(500, title='Unable to find response in '
             'cache using session: {0}:{1}, response_ids: {2}'.format(
              scenario_key, session_name, response_ids))
    
    # get latest delay policy
    delay_policy = stub.delay_policy()
    if delay_policy:
        delay = calculate_delay(delay_policy)
        if delay:
            msg = 'apply delay: {0} => {1}'.format(delay_policy, delay)
            log.debug(msg) 
            handler.track['delay'] = delay 
            trace_response.info(msg)
               
    trace_response.info('found response') 
    module_system_date = as_date(module_system_date) if module_system_date \
        else module_system_date      
    stub, _ = transform(stub, 
                        stubo_request,
                        module_system_date=module_system_date, 
                        system_date=as_date(system_date),
                        function='get/response',
                        cache=user_cache,
                        hooks=handler.settings['hooks'],
                        stage='response',
                        trace=trace_response,
                        url_args=url_args)
    transfomed_response_text = stub.response_body()[0]   
    # Note transformed_response_text can be encoded in utf8
    if response_text[0] != transfomed_response_text:
        trace_response.diff('response:transformed',
                            dict(response=response_text[0]),
                            dict(response=transfomed_response_text)) 
                                     
    return transfomed_response_text

def delete_stubs(handler, scenario_name=None, host=None, force=False):
    """delete all data relating to one named scenario or host/s."""
    log.debug('delete_stubs')
    response = {
        'version' : version
    }   
    scenario_db = Scenario()
    static_dir = handler.settings['static_path']
    
    def delete_scenario(scenario_name_key, force):
        log.debug(u'delete_scenario: {0}'.format(scenario_name_key))
        host, scenario_name = scenario_name_key.split(':')
        cache = Cache(host)
        if not force:
            active_sessions = cache.get_active_sessions(scenario_name, 
                                                        local=False)
            if active_sessions:
                raise exception_response(400, 
                    title='E016: Sessons in playback/record, can'
                    'not delete. Found the following active sessions: {0} for '
                    'scenario: {1}'.format(active_sessions, scenario_name))     
          
        scenario_db.remove_all(scenario_name_key) 
        cache.delete_caches(scenario_name)
    
    scenarios = []
    if scenario_name:
        # if scenario_name exists it takes priority 
        hostname = host or get_hostname(handler.request) 
        scenarios.append(':'.join([hostname, scenario_name]))
    elif host:
        if host == 'all':
            scenarios = [x['name'] for x in scenario_db.get_all()]
            export_dir = os.path.join(static_dir, 'exports')
            if os.path.exists(export_dir):
                log.info('delete export dir')
                shutil.rmtree(export_dir)
        else:
            # get all scenarios for host
            scenarios = [x['name'] for x in scenario_db.get_all(
                {'$regex': '{0}:.*'.format(host)})]
    else:
        raise exception_response(400, 
                                 title='scenario or host argument required')     
    for scenario_name_key in scenarios:
        delete_scenario(scenario_name_key, force)
             
    response['data'] = dict(message='stubs deleted.', scenarios=scenarios)
    return response
                                               
def begin_session(handler, scenario_name, session_name, mode, system_date=None,
                  warm_cache=False):
    log.debug('begin_session')
    response = {
        'version' : version
    }
    scenario_col = Scenario()
    cache = Cache(get_hostname(handler.request))
    if cache.blacklisted():
        raise exception_response(400, title="Sorry the host URL '{0}' has been "
         "blacklisted. Please contact Stub-O-Matic support.".format(cache.host))
    scenario_name_key = cache.scenario_key_name(scenario_name)
    scenario = scenario_col.get(scenario_name_key) 
    cache.assert_valid_session(scenario_name, session_name)      
    if mode == 'record':
        log.debug('begin_session, mode=record')
        # precond: delete/stubs?scenario={scenario_name} 
        if scenario:
            err = exception_response(400, 
              title='Duplicate scenario found - {0}'.format(scenario_name_key))
            raise err
        if scenario_col.stub_count(scenario_name_key) != 0:
            raise exception_response(500, 
              title='stub_count !=0 for scenario: {0}'.format(
                                                            scenario_name_key))
        scenario_id = scenario_col.insert(name=scenario_name_key)
        log.debug('new scenario: {0}'.format(scenario_id))
        session_payload = { 
            'status' : 'record',
            'scenario' : scenario_name_key,
            'scenario_id' : str(scenario_id),
            'session' : str(session_name)
        }
        cache.set_session(scenario_name, session_name, session_payload)      
        log.debug('new redis session: {0}:{1}'.format(scenario_name_key,
                                                      session_name))
        response["data"] = {
            'message' : 'Record mode initiated....',                
        }
        response["data"].update(session_payload)
        cache.set_session_map(scenario_name, session_name) 
        log.debug('finish record')
       
    elif mode == 'playback':
        if not scenario:
            raise exception_response(400,
              title='Scenario not found - {0}'.format(scenario_name_key))
        recordings = cache.get_sessions_status(scenario_name, 
                                               status=('record'), 
                                               local=False)
        if recordings: 
            raise exception_response(400, title='Scenario recordings taking ' \
              'place - {0}. Found the following record sessions: {1}'.format(
                                            scenario_name_key, recordings))
        cache.create_session_cache(scenario_name, session_name, system_date)
        if warm_cache:
            # iterate over stubs and call get/response for each stub matchers
            # to build the request & request_index cache
            # reset request_index to 0
            log.debug("warm cache for session '{0}'".format(session_name))
            scenario_col = Scenario()
            for payload in scenario_col.get_stubs(scenario_name_key):
                stub = Stub(payload['stub'], scenario_name_key)
                mock_request = " ".join(stub.contains_matchers())
                handler.request.body = mock_request
                get_response(handler, session_name)
            cache.reset_request_index(scenario_name)        

        response["data"] = {
            "message" : "Playback mode initiated...."
        }  
        response["data"].update({ 
            "status" : "playback",
            "scenario" : scenario_name_key,
            "session" : str(session_name)
        })
    else:
        raise exception_response(400,
                                 title='Mode of playback or record required') 
    return response
    
def end_session(handler, session_name):
    response = {
        'version' : version
    }
    cache = Cache(get_hostname(handler.request))
    scenario_key = cache.get_scenario_key(session_name)
    if not scenario_key:
        # end/session?session=x called before begin/session
        response['data'] = {
            'message' : 'Session ended'
        }
        return response
    
    host, scenario_name = scenario_key.split(':')
    # if session exists it can only be dormant
    session = cache.get_session(scenario_name, session_name, local=False)
    if not session:
        # end/session?session=x called before begin/session
        response['data'] = {
            'message' : 'Session ended'
        }
        return response
    
    handler.track.scenario = scenario_name
    session_status = session['status']
    if session_status not in ('record', 'playback'):
        log.warn('expecting session={0} to be in record of playback for '
                 'end/session'.format(session_name))
        
    session['status'] = 'dormant'
    # clear stubs cache & scenario session data
    session.pop('stubs', None)    
    cache.set(scenario_key, session_name, session)
    cache.delete_session_data(scenario_name, session_name)      
    response['data'] = {
        'message' : 'Session ended'
    }
    return response

def end_sessions(handler, scenario_name):
    response = {
        'version' : version,
        'data' : {}
    }
    cache = Cache(get_hostname(handler.request))
    sessions = list(cache.get_sessions_status(scenario_name, 
                                              status=('record', 'playback')))
    for session_name, session in sessions:
        session_response = end_session(handler, session_name)
        response['data'][session_name] = session_response.get('data')
    return response    

def update_delay_policy(handler, doc):
    """Record delay policy in redis to be available globally to any
    users for their sessions.
    put/delay_policy?name=rtz_1&delay_type=fixed&milliseconds=700
    put/delay_policy?name=rtz_2&delay_type=normalvariate&mean=100&stddev=50
    """
    cache = Cache(get_hostname(handler.request))
    response = {
        'version' : version
    }
    err = None
    if 'name' not in doc:
        err = "'name' param not found in request"
    if 'delay_type' not in doc:
        err = "'delay_type' param not found in request"
    if doc['delay_type'] == 'fixed':
        if 'milliseconds' not in doc:
            err = "'milliseconds' param is required for 'fixed' delays"
    elif doc['delay_type'] == 'normalvariate':
        if 'mean' not in doc or 'stddev' not in doc:
            err = "'mean' and 'stddev' params are required for " \
              "'normalvariate' delays"
    else:
        err = 'Unknown delay type: {0}'.format(doc['delay_type'])
    if err:
         raise exception_response(400,
            title=u'put/delay_policy arg error: {0}'.format(err))
    result = cache.set_delay_policy(doc['name'], doc)
    updated = 'new' if result else 'updated'
    response['data'] = {
        'message' : 'Put Delay Policy Finished',
        'name' : doc['name'],
        'delay_type' : doc['delay_type'],
        'status' : updated
    }
    return response

def get_delay_policy(handler, name, cache_loc):
    cache = Cache(get_hostname(handler.request))
    response = {
        'version' : version
    } 
    delay = cache.get_delay_policy(name, cache_loc)
    response['data'] = delay or {}
    return response

def delete_delay_policy(handler, names):
    cache = Cache(get_hostname(handler.request))
    response = {
        'version' : version
    } 
    num_deleted = cache.delete_delay_policy(names)
    response['data'] = {
       'message' : 'Deleted {0} delay policies from {1}'.format(num_deleted,
                                                                names)
    }
    return response

def put_setting(handler, setting, value, host):
    response = {
        'version' : version
    } 
    all_hosts = True if host == 'all' else False
    if all_hosts:
        host = get_hostname(handler.request)
    cache = Cache(host)
    new_setting = cache.set_stubo_setting(setting, value, all_hosts)
    response['data'] = {
        'host' : host, 
        'all' : all_hosts,
        'new' : 'true' if new_setting else 'false', setting : value
    }                     
    return response   

def get_setting(handler, host, setting=None):
    all_hosts = True if host == 'all' else False
    if all_hosts:
        host = get_hostname(handler.request)
    cache = Cache(host)
    result = cache.get_stubo_setting(setting, all_hosts)   
    response = dict(version=version, data=dict(host=host, all=all_hosts))
    if setting:
        response['data'][setting] = result
    else:
        response['data']['settings'] = result      
    return response                         

def get_status(handler):
    """Check status. 
       query args: 
         scenario=name 
         session=name
         check_database=true|false (default true)
         local_cache=true|false (default true)
    """
    request = handler.request
    cache = Cache(get_hostname(request))
    response = dict(version=version, data={})   
    args = dict((key, value[0]) for key, value in request.arguments.iteritems()) 
    local_cache = asbool(args.get('local_cache', True))
    redis_server = get_redis_server(local_cache)
    response['data']['cache_server'] = {'local' : local_cache}
    response['data']['info'] = {
        'cluster' : handler.settings.get('cluster_name'),
        'graphite_host' : handler.settings.get('graphite.host')
    }

    try:
        result = redis_server.ping()
        response['data']['cache_server']['status'] = 'ok' if result else 'bad'   
    except Exception, e:
        response['data']['cache_server']['status'] = 'bad'
        response['data']['cache_server']['error'] = str(e)
        return response   
        
    scenario_name = args.get('scenario')
    session_name = args.get('session')
    # session takes precedence
    if session_name:
        scenario_key = cache.get_scenario_key(session_name)
        session = {}
        if scenario_key:
            session = cache.get_session(scenario_key.partition(':')[-1], 
                                        session_name)
        response['data']['session'] = session 
    elif scenario_name:
        sessions = list(cache.get_sessions_status(scenario_name, 
                                                  local=local_cache))
        response['data']['sessions'] = sessions
    
    check_database = asbool(args.get('check_database', True))
    if check_database:
        response['data']['database_server'] = {'status' : 'bad'}
        try:
            if get_mongo_client().connection.alive():
                response['data']['database_server']['status'] = 'ok'
        except:
            response['data']['database_server']['error'] = "mongo down"
    return response

def put_bookmark(handler, session_name, name):
    cache = Cache(get_hostname(handler.request)) 
    response = dict(version=version, data = {}) 
    if not session_name:
        raise exception_response(400, title="No session provided")
            
    scenario_key = cache.find_scenario_key(session_name)
    scenario_name = scenario_key.partition(':')[-1]         
               
    # retrieve the request index state for selected session
    index_state = {}
    request_index_data = cache.get_request_index_data(scenario_name)
    if request_index_data:
        for k, v in  request_index_data.iteritems():
            indexed_session_name, _, stub_key = k.partition(':')
            if indexed_session_name == session_name:
                index_state[stub_key] = v          
        
    if not index_state:
        raise exception_response(400,
            title="No indexes found for session '{0}'. Is the session in "
            'playback mode and have state?'.format(session_name)) 
    log.debug("save request index state '{0}' = {1}".format(name, index_state))
    cache.set_saved_request_index_data(scenario_name, name, index_state)
    response['data'][name] = index_state
    return response   

def get_bookmark(handler, scenario_name, name):
    cache = Cache(get_hostname(handler.request)) 
    response = dict(version=version, data={}) 
    index_state = cache.get_saved_request_index_data(scenario_name, name)
    response['data'][name] = index_state 
    return response

def get_bookmarks(handler):
    cache = Cache(get_hostname(handler.request))
    response = dict(version=version, data={}) 
    all_index_state = cache.get_all_saved_request_index_data()
    response['data'] = all_index_state 
    return response   

def delete_bookmark(handler, name, scenario):
    cache = Cache(get_hostname(handler.request))
    response = dict(version=version, data={}) 
    result = cache.delete_saved_request_index(scenario, name)
    response['data'] = {'bookmark' : name, 'deleted' : result}
    return response            

def check_bookmark(host, bookmark_name, bookmark):
    if not bookmark:
        raise exception_response(400, 
          title='No bookmarks have been saved {0}'.format(
                                         self.get_saved_request_index_key())) 
        
def jump_bookmark(handler, name, sessions, index=None):
    request = handler.request
    cache = Cache(get_hostname(request)) 
    response = dict(version=version, data = {})
    scenario_key = cache.find_scenario_key(host, sessions[0])
    scenario_name = scenario_key.partition(':')[-1]
    if not all(cache.find_scenario_key(host, x) == scenario_key for x in sessions):
        raise exception_response(400,
          title="All sessions must belong to the same scenario")  
           
    index_state = cache.get_saved_request_index_data(scenario_name, name)
    check_bookmark(host, name, index_state)
    results = []
    for session in sessions:
        for k, v in index_state.iteritems():
            v = v if index is None else index
            session_key = '{0}:{1}'.format(session, k)
            result = set_request_index_item(scenario_name, session_key, v)
            results.append((k, v, result))  
    response['data']['results'] = results
    return response 

def import_bookmarks(handler, location):
    request = handler.request
    cache = Cache(get_hostname(request)) 
    response = dict(version=version, data={})
    uri, bookmarks_name = UriLocation(request)(location)
    log.info('uri={0}, bookmarks_name={1}'.format(uri, bookmarks_name))
    payload, _ = UrlFetch().get(uri)
    payload = json.loads(payload)
    # e.g payload
    #{"converse":  {"first": {"8981c0dda19403f5cc054aea758689e65db2": "2"}}} 
    imported = {}
    for scenario, bookmarks in payload.iteritems():
        for bookmark_name, bookmark in bookmarks.iteritems():
            is_new = cache.set_saved_request_index_data(scenario, bookmark_name,
                                                        bookmark)
            scenario_book = '{0}:{1}'.format(scenario, bookmark_name)
            imported[scenario_book] = ('new' if is_new else 'updated', bookmark)    
    response['data']['imported'] = imported
    return response

def bookmarks_request_api(handler):
    hostname = get_hostname(handler.request)
    message = error_message = ""
    name = handler.get_argument('name', None)
    if name is not None:
        try:
            action = handler.get_argument('action', None)
            scenario = handler.get_argument('scenario', None)
            if action == 'delete':
                result = delete_bookmark(handler, name, scenario)
                if result['data']['deleted']:
                    message = "deleted {0}".format(name) 
                else:
                    error_message = "Unable to delete bookmark '{0}', does "\
                    "it still exist?".format(name)
            elif action == 'jump':
                index = handler.get_argument('index', None)
                sessions = handler.get_arguments('session')
                if sessions:    
                    result = jump_bookmark(handler, name, sessions, index)
                    if index:
                        message = 'jumped to start'
                    else:
                        message = 'jumped to bookmark {0}'.format(name) 
                    message += ' for sessions "{0}"'.format(", ".join(sessions))                                         
                else:
                    error_message = "You must pick a session"                           
            else:        
                # form POST to create a new bookmark
                if name:
                    session = handler.get_argument('session', None)
                    result = put_bookmark(handler, session, name)
                    message = "created {0} bookmark".format(name)
                else:
                    message = "You must supply a Name to create a new bookmark"
        except StuboException, e:
            error_message = "Error: {0}".format(e.title)
    
    response = get_bookmarks(handler)
    status = get_session_status(handler, all_hosts=False).get(hostname)
    active = {}
    if status:
        for scenario_name, session_info in status.iteritems():
            sessions = session_info[0]          
            for session in sessions:
                session_name = session['session']
                if session['status'] == 'playback':
                    stateful_stubs = [x for x in session['stubs'] if len(
                        StubCache(x, scenario_name, session).response_ids()) > 1]
                    if stateful_stubs:
                        if scenario_name not in active:
                            active[scenario_name] = [session_name] 
                        else:       
                            active[scenario_name].append(session_name) 
    if not active:
        message = '{0} does not have any active playback sessions'.format(
                                                            hostname)
        
    return dict(bookmarks=response['data'],
                active=active,
                message=message,
                error_message=error_message,
                page_name = 'Bookmarks') 
                                     

def manage_request_api(handler):
    cache = Cache(get_hostname(handler.request)) 
    action = handler.get_argument('action', None)
    all_hosts = asbool(handler.get_argument("all_hosts", False))
    message = error_message = ""
    module_info = {}
    if action is not None:
        # handle btn action 
        try:
            name = handler.get_argument('name')
            # It would be nice to really track these actions
            handler.track = DummyModel()
            if action == 'delete':
                _type = handler.get_argument('type')
                if _type == 'module':
                    result = delete_module(handler.request, [name])
                elif _type == 'delay_policy':
                    result = delete_delay_policy(handler, [name])
                elif _type == 'stubs':
                    result = delete_stubs(handler, scenario_name=name,
                                          host=all_hosts)    
                else:
                    result = 'error: unexpected action type={0}'.format(_type)
            elif action == 'end_session':
                result = end_session(handler, name)
            elif action == 'end_sessions':
                result = end_sessions(handler, name)    
            else:
                result = 'error: unexpected action={0}'.format(action)
                            
            if 'error' not in result:
                message = result
            else:
                error_message = result
        except MissingArgumentError, e:
            error_message = "Error: {0}".format(e)   
        except StuboException, e:
            error_message = "Error: {0}".format(e.title)       
    
    cmdFile = handler.get_argument('cmdFile', '') 
    http_req = handler.request
    response = dict(host_scenarios=get_session_status(handler, 
                                                      all_hosts=all_hosts))                                                 
    cache_loc = handler.get_argument('cache', 'master') 
    response['delays'] = get_delay_policy(handler, None, cache_loc).get('data')
    modules = list_module(handler, None)['data'].get('info')
    for name in modules.keys():
        source_text = pretty_format_python(Module(cache.host).get_source(name))
        modules[name]['code'] = source_text
    response['modules'] = modules
    response['cmdFile'] = cmdFile
    response['message'] = message
    response['error_message'] = error_message
    response['module_info'] =  module_info
    response['stubo_version'] = version
    response['host'] = cache.host
    response['page_name'] = 'Manage'
    return response

def get_session_status(handler, all_hosts=True):
    scenario = Scenario()
    host_scenarios = {}
    for s in scenario.get_all():
        host, scenario_name = s['name'].split(':')
        if not all_hosts and get_hostname(handler.request)  != host:
            continue
        if host not in host_scenarios:
            host_scenarios[host] = {}
        sessions = []
        cache = Cache(host)
        for session_name, session in cache.get_sessions(scenario_name):
            # try and get the last_used from the last tracker get/response
            # else when the begin/session playback was called
            last_used = session_last_used(s['name'], session_name)
            if last_used:
                last_used = last_used['start_time'].strftime('%Y-%m-%d %H:%M:%S')
            else: 
                # session has never been used for playback   
                last_used = session.get('last_used', '-')
            session['last_used'] =  last_used  
            sessions.append(session)   
        stub_counts =  stub_count(host, scenario_name)['data']['count']
        recorded = '-'
        space_used = 0
        if sessions:
            if stub_counts:
                stubs = list(get_stubs(host, scenario_name))
                recorded =  max(x['stub'].get('recorded') for x in stubs)   
                for stub in stubs:
                    stub = Stub(stub['stub'], s['name']) 
                    for matcher in stub.contains_matchers():
                        space_used += len(matcher)
                    space_used += stub.space_used()             
                host_scenarios[host][scenario_name] = (sessions, stub_counts, 
                                            recorded, human_size(space_used)) 
            else:
                host_scenarios[host][scenario_name] = (sessions, 0, '-', 0)        
    return host_scenarios  
   
