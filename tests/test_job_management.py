import shutil

import pytest
import requests
import json
import os
import time
import jwt
import logging
import email
from urllib.parse import urlencode
import glob

logger = logging.getLogger(__name__)
# symmetric shared secret for the decoding of the token
secret_key = 'secretkey_test'

default_exp_time = int(time.time()) + 5000
default_token_payload = dict(
    sub="mtm@mtmco.net",
    name="mmeharga",
    roles="general",
    exp=default_exp_time,
    tem=0,
    mstout=True,
    mssub=True,
    intsub=5
)


def test_callback_without_prior_run_analysis(dispatcher_live_fixture):
    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    c = requests.get(server + "/call_back",
                     params={
                         'job_id': 'test-job-id',
                         'instrument_name': 'test-instrument_name',
                     })

    logger.info(c.text)

    assert c.status_code == 200


def test_public_async_request(dispatcher_live_fixture, dispatcher_local_mail_server):
    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    dict_param = dict(
        query_status="new",
        query_type="Real",
        instrument="empty-async",
        product_type="dummy"
    )

    # this should return status submitted, so email sent
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))

    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert 'email_status' not in jdata['exit_status']

    session_id = c.json()['session_id']
    job_id = c.json()['job_monitor']['job_id']

    c = requests.get(server + "/run_analysis",
                     params=dict(
                         query_status="ready",  # whether query is new or not, this should work
                         query_type="Real",
                         instrument="empty-async",
                         product_type="dummy",
                         async_dispatcher=False,
                         session_id=session_id,
                         job_id=job_id,
                     ))

    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert 'email_status' not in jdata['exit_status']


@pytest.mark.not_safe_parallel
@pytest.mark.parametrize("default_values", [True, False])
@pytest.mark.parametrize("time_original_request_none", [True, False])
@pytest.mark.parametrize("request_cred", ['public', 'private'])
def test_email_callback_after_run_analysis(dispatcher_live_fixture, dispatcher_local_mail_server, default_values, request_cred, time_original_request_none):
    # TODO: for now, this is not very different from no-prior-run_analysis. This will improve

    # remove all the current scratch folders
    dir_list = glob.glob('scratch_*')
    [shutil.rmtree(d) for d in dir_list]

    token_none = ( request_cred == 'public' )
        
    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    # email content in plain text and html format
    plain_text_email = "Update of the task submitted at {time_request_str}, for the instrument empty-async:\n* status {status}\nProducts url {request_url}"
    html_text_email = "<html><body><p>Update of the task submitted at {time_request_str}, for the instrument empty-async:<br><ul><li>status {status}</li></ul>Products url {request_url}</p></body></html>"""
    smtp_server_log = f'local_smtp_log/{dispatcher_local_mail_server.id}_local_smtp_output.json'
    email_subject = "[ODA][{status}] Request for {product_type} created at {time_request_str} {job_id}"

    if token_none:
        encoded_token = None
    else:
        # let's generate a valid token with high threshold
        token_payload = {
            **default_token_payload,
            "tem": 0
        }

        if default_values:
            token_payload.pop('tem')
            token_payload.pop('mstout')
            token_payload.pop('mssub')
            token_payload.pop('intsub')

        encoded_token = jwt.encode(token_payload, secret_key, algorithm='HS256')

    dict_param = dict(
        query_status="new",
        query_type="Real",
        instrument="empty-async",
        product_type="dummy",
        token=encoded_token
    )

    # this should return status submitted, so email sent
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))

    session_id = c.json()['session_id']
    job_id = c.json()['job_monitor']['job_id']
    dict_param_complete = dict_param.copy()
    # dict_param_complete['session_id'] = session_id
    dict_param_complete.pop("token")

    assert 'session_id' not in dict_param_complete
    assert 'job_id' not in dict_param_complete
    assert 'token' not in dict_param_complete

    products_url = '%s?%s' % ('http://www.astro.unige.ch/cdci/astrooda_', urlencode(dict_param_complete))

    job_monitor_json_fn = f'scratch_sid_{session_id}_jid_{job_id}/job_monitor.json'
    # the aliased version might have been created
    job_monitor_json_fn_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor.json'
    assert os.path.exists(job_monitor_json_fn) or os.path.exists(job_monitor_json_fn_aliased)
    if os.path.exists(job_monitor_json_fn):
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}/email_history'
    else:
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}_aliased/email_history'

    assert c.status_code == 200
    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    # get the original time the request was made
    assert 'time_request' in jdata
    # set the time the request was initiated
    time_request = jdata['time_request']
    time_request_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(time_request)))

    if token_none:
        # email not supposed to be sent for public request
        assert 'email_status' not in jdata
    else:
        assert jdata['exit_status']['email_status'] == 'email sent'

        # check the email in the email folders, and that the first one was produced
        assert os.path.exists(email_history_folder_path)
        list_email_files = glob.glob(email_history_folder_path + '/email_submitted_*.email')
        assert len(list_email_files) == 1

        assert os.path.exists(smtp_server_log)
        f_local_smtp = open(smtp_server_log)
        f_local_smtp_jdata = json.load(f_local_smtp)

        assert len(f_local_smtp_jdata) == 1
        assert f_local_smtp_jdata[0]['mail_from'] == 'team@odahub.io'
        assert f_local_smtp_jdata[0]['rcpt_tos'] == ['mtm@mtmco.net', 'team@odahub.io']
        data_email = f_local_smtp_jdata[0]['data']
        msg = email.message_from_string(data_email)
        assert msg['Subject'] == email_subject.format(time_request_str=time_request_str, status="submitted",
                                                      product_type="dummy", job_id=job_id[:8])
        assert msg['From'] == 'team@odahub.io'
        assert msg['To'] == 'mtm@mtmco.net'
        assert msg['CC'] == ", ".join(['team@odahub.io'])
        assert msg.is_multipart()
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                content_text_plain = part.get_payload().replace('\r', '').strip()
                assert content_text_plain == plain_text_email.format(time_request_str=time_request_str, status="submitted",
                                                                    request_url=products_url)
            if part.get_content_type() == 'text/html':
                content_text_html = part.get_payload().replace('\r', '').strip()
                assert content_text_html == html_text_email.format(time_request_str=time_request_str, status="submitted",
                                                                        request_url=products_url)

    # for the call_back(s) in case the time of the original request is not provided
    if time_original_request_none:
        time_request = None
        time_request_str = 'None'
        plain_text_email = "Update of the task for the instrument empty-async:\n* status {status}\nProducts url {request_url}"
        html_text_email = "<html><body><p>Update of the task for the instrument empty-async:<br><ul><li>status {status}</li></ul>Products url {request_url}</p></body></html>"""
        email_subject = "[ODA][{status}] Request for {product_type} {job_id}"

    for i in range(5):
        # imitating what a backend would do
        c = requests.get(server + "/call_back",
                         params=dict(
                             job_id=job_id,
                             session_id=session_id,
                             instrument_name="empty-async",
                             action='progress',
                             node_id=f'node_{i}',
                             message='progressing',
                             token=encoded_token,
                             time_original_request=time_request
                         ))

    c = requests.get(server + "/call_back",
                     params=dict(
                         job_id=job_id,
                         session_id=session_id,
                         instrument_name="empty-async",
                         action='ready',
                         node_id='node_ready',
                         message='ready',
                         token=encoded_token,
                         time_original_request=time_request
                     ))

    # this triggers email
    c = requests.get(server + "/call_back",
                     params=dict(
                         job_id=job_id,
                         session_id=session_id,
                         instrument_name="empty-async",
                         action='done',
                         node_id='node_final',
                         message='done',
                         token=encoded_token,
                         time_original_request=time_request
                     ))

    # TODO build a test that effectively test both paths
    job_monitor_call_back_done_json_fn = f'scratch_sid_{session_id}_jid_{job_id}/job_monitor_node_final_done_.json'
    # the aliased version might have been created
    job_monitor_call_back_done_json_fn_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor_node_final_done_.json'
    assert os.path.exists(job_monitor_call_back_done_json_fn) or \
           os.path.exists(job_monitor_call_back_done_json_fn_aliased)
    assert c.status_code == 200
    # read the json file
    if os.path.exists(job_monitor_call_back_done_json_fn):
        f = open(job_monitor_call_back_done_json_fn)
    else:
        f = open(job_monitor_call_back_done_json_fn_aliased)

    jdata = json.load(f)
    # if default_values or token_none or time_request_none:
    if default_values or token_none or time_original_request_none:
        # for this case, email not supposed to be sent if request is short and/or no time information are available
        # or public request
        assert 'email_status' not in jdata
    else:
        assert jdata['email_status'] == 'email sent'

        # check the email in the email folders, and that the first one was produced
        assert os.path.exists(email_history_folder_path)
        list_email_files = glob.glob(email_history_folder_path + '/email_done_*.email')
        assert len(list_email_files) == 1

        # check the email in the log files
        assert os.path.exists(smtp_server_log)
        f_local_smtp = open(smtp_server_log)
        f_local_smtp_jdata = json.load(f_local_smtp)
        assert len(f_local_smtp_jdata) == 2
        assert f_local_smtp_jdata[1]['mail_from'] == 'team@odahub.io'
        assert f_local_smtp_jdata[1]['rcpt_tos'] == ['mtm@mtmco.net', 'team@odahub.io']
        data_email = f_local_smtp_jdata[1]['data']
        msg = email.message_from_string(data_email)
        assert msg['Subject'] == email_subject.format(time_request_str=time_request_str, status="done",
                                                      product_type="dummy", job_id=job_id[:8])
        assert msg['From'] == 'team@odahub.io'
        assert msg['To'] == 'mtm@mtmco.net'
        assert msg['CC'] == ", ".join(['team@odahub.io'])
        assert msg.is_multipart()
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                content_text_plain = part.get_payload().replace('\r', '').strip()
                assert content_text_plain == plain_text_email.format(time_request_str=time_request_str, status="done",
                                                                    request_url=products_url)
            if part.get_content_type() == 'text/html':
                content_text_html = part.get_payload().replace('\r', '').strip()
                assert content_text_html == html_text_email.format(time_request_str=time_request_str, status="done",
                                                                request_url=products_url)

    # this also triggers email (simulate a failed request)
    c = requests.get(server + "/call_back",
                     params={
                         'job_id': job_id,
                         'session_id': session_id,
                         'instrument_name': "empty-async",
                         'action': 'failed',
                         'node_id': 'node_failed',
                         'message': 'failed',
                         'token': encoded_token,
                         'time_original_request': time_request
                     })
    job_monitor_call_back_failed_json_fn = f'scratch_sid_{session_id}_jid_{job_id}/job_monitor_node_failed_failed_.json'
    # the aliased version might have been created
    job_monitor_call_back_failed_json_fn_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor_node_failed_failed_.json'

    assert os.path.exists(job_monitor_call_back_failed_json_fn) or os.path.exists(
        job_monitor_call_back_failed_json_fn_aliased)
    assert c.status_code == 200
    # read the json file
    if os.path.exists(job_monitor_call_back_failed_json_fn):
        f = open(job_monitor_call_back_failed_json_fn)
    else:
        f = open(job_monitor_call_back_failed_json_fn_aliased)

    jdata = json.load(f)

    if token_none:
        # email not supposed to be sent for public request
        assert 'email_status' not in jdata
    else:
        assert jdata['email_status'] == 'email sent'

        # check the email in the email folders, and that the first one was produced
        assert os.path.exists(email_history_folder_path)
        # if default_values or time_original_request_none:
        #     list_email_files = glob.glob(email_history_folder_path + '/email_1_failed_*.email')
        #     assert len(list_email_files) == 1
        # else:
        list_email_files = glob.glob(email_history_folder_path + '/email_failed_*.email')
        assert len(list_email_files) == 1

        # check the email in the log files
        assert os.path.exists(smtp_server_log)
        f_local_smtp = open(smtp_server_log)
        f_local_smtp_jdata = json.load(f_local_smtp)
        # if default_values or time_request_none:
        if default_values or time_original_request_none:
            assert len(f_local_smtp_jdata) == 2
        else:
            assert len(f_local_smtp_jdata) == 3
        assert f_local_smtp_jdata[len(f_local_smtp_jdata) - 1]['mail_from'] == 'team@odahub.io'
        assert f_local_smtp_jdata[len(f_local_smtp_jdata) - 1]['rcpt_tos'] == ['mtm@mtmco.net', 'team@odahub.io']
        data_email = f_local_smtp_jdata[len(f_local_smtp_jdata) - 1]['data']
        msg = email.message_from_string(data_email)
        assert msg['Subject'] == email_subject.format(time_request_str=time_request_str, status="failed",
                                                      product_type="dummy", job_id=job_id[:8])
        assert msg['From'] == 'team@odahub.io'
        assert msg['To'] == 'mtm@mtmco.net'
        assert msg['CC'] == ", ".join(['team@odahub.io'])
        assert msg.is_multipart()
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                content_text_plain = part.get_payload().replace('\r', '').strip()
                assert content_text_plain == plain_text_email.format(time_request_str=time_request_str, status="failed",
                                                                    request_url=products_url)
            if part.get_content_type() == 'text/html':
                content_text_html = part.get_payload().replace('\r', '').strip()
                assert content_text_html == html_text_email.format(time_request_str=time_request_str, status="failed",
                                                                    request_url=products_url)

    # TODO this will rewrite the value of the time_request in the query output, but it shouldn't be a problem?
    # This is not complete since DataServerQuery never returns done
    c = requests.get(server + "/run_analysis",
                     params=dict(
                         query_status="ready",  # whether query is new or not, this should work
                         query_type="Real",
                         instrument="empty-async",
                         product_type="dummy",
                         async_dispatcher=False,
                         session_id=session_id,
                         job_id=job_id,
                         token=encoded_token
                     ))

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))
    # jdata = c.json()
    # TODO: test that this returns entire log
    # full_report_dict_list = c.json()['job_monitor'].get('full_report_dict_list')
    # assert len(full_report_dict_list) == 5

    assert c.status_code == 200

    # TODO: test that this returns the result


@pytest.mark.not_safe_parallel
def test_email_submitted_same_job(dispatcher_live_fixture, dispatcher_local_mail_server):
    # remove all the current scratch folders
    dir_list = glob.glob('scratch_*')
    [shutil.rmtree(d) for d in dir_list]

    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    # email content in plain text and html format
    smtp_server_log = f'local_smtp_log/{dispatcher_local_mail_server.id}_local_smtp_output.json'

    # let's generate a valid token with high threshold
    token_payload = {
        **default_token_payload,
        "intsub": 15
    }

    encoded_token = jwt.encode(token_payload, secret_key, algorithm='HS256')

    dict_param = dict(
        query_status="new",
        query_type="Real",
        instrument="empty-async",
        product_type="dummy",
        token=encoded_token
    )

    # this should return status submitted, so email sent
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))

    session_id = c.json()['session_id']
    job_id = c.json()['job_monitor']['job_id']
    dict_param_complete = dict_param.copy()
    # dict_param_complete['session_id'] = session_id
    dict_param_complete.pop("token")

    job_monitor_json_fn = f'scratch_sid_{session_id}_jid_{job_id}/job_monitor.json'
    # the aliased version might have been created
    job_monitor_json_fn_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor.json'
    assert os.path.exists(job_monitor_json_fn) or os.path.exists(job_monitor_json_fn_aliased)
    if os.path.exists(job_monitor_json_fn):
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}/email_history'
    else:
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}_aliased/email_history'

    assert c.status_code == 200
    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert jdata['exit_status']['email_status'] == 'email sent'

    # check the email in the email folders, and that the first one was produced
    assert os.path.exists(email_history_folder_path)
    list_email_files = glob.glob(email_history_folder_path + '/email_submitted_*.email')
    assert len(list_email_files) == 1

    assert os.path.exists(smtp_server_log)
    f_local_smtp = open(smtp_server_log)
    f_local_smtp_jdata = json.load(f_local_smtp)

    assert len(f_local_smtp_jdata) == 1

    # re-submit the very same request, in order to produce a sequence of submitted status
    # and verify not a sequence of emails are generated
    dict_param = dict(
        query_status="new",
        query_type="Real",
        instrument="empty-async",
        product_type="dummy",
        session_id=session_id,
        job_id=job_id,
        token=encoded_token
    )

    for i in range(5):
        c = requests.get(server + "/run_analysis",
                         dict_param
                         )

        assert c.status_code == 200
        jdata = c.json()
        assert jdata['exit_status']['job_status'] == 'submitted'
        assert 'email_status' not in jdata['exit_status']

        # check the email in the email folders, and that the first one was produced
        assert os.path.exists(email_history_folder_path)
        list_email_files = glob.glob(email_history_folder_path + '/email_submitted_*.email')
        assert len(list_email_files) == 1

        assert os.path.exists(smtp_server_log)
        f_local_smtp = open(smtp_server_log)
        f_local_smtp_jdata = json.load(f_local_smtp)

        assert len(f_local_smtp_jdata) == 1

    # let the interval time pass, so that a new email si sent
    time.sleep(16)
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    assert c.status_code == 200
    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert jdata['exit_status']['email_status'] == 'email sent'

    # check the email in the email folders, and that the first one was produced
    assert os.path.exists(email_history_folder_path)
    list_email_files = glob.glob(email_history_folder_path + '/email_submitted_*.email')
    assert len(list_email_files) == 2

    assert os.path.exists(smtp_server_log)
    f_local_smtp = open(smtp_server_log)
    f_local_smtp_jdata = json.load(f_local_smtp)

    assert len(f_local_smtp_jdata) == 2

    # let the interval time pass again, so that a new email si sent
    time.sleep(16)
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    assert c.status_code == 200
    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert jdata['exit_status']['email_status'] == 'email sent'

    # check the email in the email folders, and that the first one was produced
    assert os.path.exists(email_history_folder_path)
    list_email_files = glob.glob(email_history_folder_path + '/email_submitted_*.email')
    assert len(list_email_files) == 3

    assert os.path.exists(smtp_server_log)
    f_local_smtp = open(smtp_server_log)
    f_local_smtp_jdata = json.load(f_local_smtp)

    assert len(f_local_smtp_jdata) == 3


@pytest.mark.not_safe_parallel
def test_email_submitted_multiple_requests(dispatcher_live_fixture, dispatcher_local_mail_server):
    # remove all the current scratch folders
    dir_list = glob.glob('scratch_*')
    [shutil.rmtree(d) for d in dir_list]

    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    # email content in plain text and html format
    smtp_server_log = f'local_smtp_log/{dispatcher_local_mail_server.id}_local_smtp_output.json'

    # let's generate a valid token with high threshold
    token_payload = {
        **default_token_payload,
        "intsub": 15
    }

    encoded_token = jwt.encode(token_payload, secret_key, algorithm='HS256')

    dict_param = dict(
        query_status="new",
        query_type="Real",
        instrument="empty-async",
        product_type="dummy",
        token=encoded_token
    )

    # this should return status submitted, so email sent
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))

    session_id = c.json()['session_id']
    job_id = c.json()['job_monitor']['job_id']

    assert os.path.exists(f'scratch_sid_{session_id}_jid_{job_id}')
    email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}/email_history'

    assert c.status_code == 200
    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert jdata['exit_status']['email_status'] == 'email sent'

    # check the email in the email folders, and that the first one was produced
    assert os.path.exists(email_history_folder_path)
    list_email_files = glob.glob(email_history_folder_path + '/email_submitted_*.email')
    assert len(list_email_files) == 1

    # re-submit the same request (so that the same job_id will be generated) but as a different session,
    # in order to produce a sequence of submitted status
    # and verify not a sequence of submitted-status emails are generated
    dict_param = dict(
        query_status="new",
        query_type="Real",
        instrument="empty-async",
        product_type="dummy",
        token=encoded_token
    )

    for i in range(5):
        c = requests.get(server + "/run_analysis",
                         dict_param
                         )

        assert c.status_code == 200
        jdata = c.json()
        assert jdata['exit_status']['job_status'] == 'submitted'
        assert 'email_status' not in jdata['exit_status']
    # jobs will be aliased
    list_email_files = glob.glob(f'scratch_sid_*_jid_{job_id}_*/email_history/email_submitted_*.email')
    assert len(list_email_files) == 0

    # let the interval time pass, so that a new email si sent
    time.sleep(16)
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    assert c.status_code == 200
    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert jdata['exit_status']['email_status'] == 'email sent'
    session_id = jdata['session_id']

    # check the email in the email folders, and that the first one was produced
    assert os.path.exists(f'scratch_sid_{session_id}_jid_{job_id}_aliased')
    list_email_files_last_request = glob.glob(f'scratch_sid_{session_id}_jid_{job_id}_aliased/email_history/email_submitted_*.email')
    assert len(list_email_files_last_request) == 1
    list_overall_email_files = glob.glob(f'scratch_sid_*_jid_{job_id}*/email_history/email_submitted_*.email')
    assert len(list_overall_email_files) == 2


@pytest.mark.not_safe_parallel
def test_email_done(dispatcher_live_fixture, dispatcher_local_mail_server):
    # remove all the current scratch folders
    dir_list = glob.glob('scratch_*')
    [shutil.rmtree(d) for d in dir_list]

    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    token_payload = {
        **default_token_payload,
        "tem": 0
    }

    encoded_token = jwt.encode(token_payload, secret_key, algorithm='HS256')

    dict_param = dict(
        query_status="new",
        query_type="Real",
        instrument="empty-async",
        product_type="dummy",
        token=encoded_token
    )

    # this should return status submitted, so email sent
    c = requests.get(server + "/run_analysis",
                     dict_param
                     )

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))
    jdata = c.json()
    session_id = jdata['session_id']
    job_id = jdata['job_monitor']['job_id']
    time_request = jdata['time_request']

    scratch_dir_path = f'scratch_sid_{session_id}_jid_{job_id}/'
    # the aliased version might have been created
    scratch_dir_path_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor.json'
    assert os.path.exists(scratch_dir_path) or os.path.exists(scratch_dir_path_aliased)
    if os.path.exists(scratch_dir_path):
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}/email_history'
    else:
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}_aliased/email_history'

    # a number of done call_backs, but only one should trigger the email sending
    for i in range(5):
        requests.get(server + "/call_back",
                     params=dict(
                         job_id=job_id,
                         session_id=session_id,
                         instrument_name="empty-async",
                         action='done',
                         node_id='node_final',
                         message='done',
                         token=encoded_token,
                         time_original_request=time_request
                         ))

    # check the email in the email folders, and that the first one was produced
    assert os.path.exists(email_history_folder_path)
    list_email_files = glob.glob(email_history_folder_path + '/email_submitted_*.email')
    assert len(list_email_files) == 1

    assert os.path.exists(email_history_folder_path)
    list_email_files = glob.glob(email_history_folder_path + '/email_done_*.email')
    assert len(list_email_files) == 1


def test_email_failure_callback_after_run_analysis(dispatcher_live_fixture):
    # TODO: for now, this is not very different from no-prior-run_analysis. This will improve

    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    # let's generate a valid token with high threshold
    token_payload = {
        **default_token_payload,
        "tem": 0
    }
    encoded_token = jwt.encode(token_payload, secret_key, algorithm='HS256')
    # set the time the request was initiated
    time_request = time.time()
    c = requests.get(server + "/run_analysis",
                     params=dict(
                         query_status="new",
                         query_type="Real",
                         instrument="empty-async",
                         product_type="dummy",
                         token=encoded_token,
                         time_request=time_request
                     ))

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))

    session_id = c.json()['session_id']
    job_id = c.json()['job_monitor']['job_id']

    # TODO ensure it is submitted

    job_monitor_json_fn = f'scratch_sid_{session_id}_jid_{job_id}/job_monitor.json'
    # the aliased version might have been created
    job_monitor_json_fn_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor.json'

    assert os.path.exists(job_monitor_json_fn) or os.path.exists(job_monitor_json_fn_aliased)
    assert c.status_code == 200

    jdata = c.json()
    assert jdata['exit_status']['email_status'] == 'sending email failed'

    # this triggers email
    c = requests.get(server + "/call_back",
                     params={
                         'job_id': job_id,
                         'session_id': session_id,
                         'instrument_name': "empty-async",
                         'action': 'failed',
                         'node_id': 'node_failed',
                         'message': 'failed',
                         'token': encoded_token,
                         'time_original_request': time_request
                     })
    job_monitor_call_back_failed_json_fn = f'scratch_sid_{session_id}_jid_{job_id}/job_monitor_node_failed_failed_.json'
    # the aliased version might have been created
    job_monitor_call_back_failed_json_fn_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor_node_failed_failed_.json'

    assert os.path.exists(job_monitor_call_back_failed_json_fn) or os.path.exists(
        job_monitor_call_back_failed_json_fn_aliased)

    assert c.status_code == 200
    # read the json file and get the path for the email history
    if os.path.exists(job_monitor_call_back_failed_json_fn):
        f = open(job_monitor_call_back_failed_json_fn)
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}/email_history'
    else:
        f = open(job_monitor_call_back_failed_json_fn_aliased)
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}_aliased/email_history'

    jdata = json.load(f)
    assert jdata['email_status'] == 'sending email failed'
    assert not os.path.exists(email_history_folder_path)


@pytest.mark.not_safe_parallel
def test_email_callback_after_run_analysis_subprocess_mail_server(dispatcher_live_fixture, dispatcher_local_mail_server_subprocess):
    # remove all the current scratch folders
    dir_list = glob.glob('scratch_*')
    [shutil.rmtree(d) for d in dir_list]

    server = dispatcher_live_fixture
    logger.info("constructed server: %s", server)

    # let's generate a valid token with high threshold
    token_payload = {
        **default_token_payload,
        "tem": 0,
    }
    encoded_token = jwt.encode(token_payload, secret_key, algorithm='HS256')
    # this should return status submitted, so email sent
    c = requests.get(server + "/run_analysis",
                     params=dict(
                         query_status="new",
                         query_type="Real",
                         instrument="empty-async",
                         product_type="dummy",
                         token=encoded_token
                     ))

    logger.info("response from run_analysis: %s", json.dumps(c.json(), indent=4))

    session_id = c.json()['session_id']
    job_id = c.json()['job_monitor']['job_id']

    job_monitor_json_fn = f'scratch_sid_{session_id}_jid_{job_id}/job_monitor.json'
    # the aliased version might have been created
    job_monitor_json_fn_aliased = f'scratch_sid_{session_id}_jid_{job_id}_aliased/job_monitor.json'

    assert os.path.exists(job_monitor_json_fn) or os.path.exists(job_monitor_json_fn_aliased)
    assert c.status_code == 200

    # read the json file and get the path for the email history
    if os.path.exists(job_monitor_json_fn):
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}/email_history'
    else:
        email_history_folder_path = f'scratch_sid_{session_id}_jid_{job_id}_aliased/email_history'

    jdata = c.json()
    assert jdata['exit_status']['job_status'] == 'submitted'
    assert jdata['exit_status']['email_status'] == 'email sent'

    assert os.path.exists(email_history_folder_path)
    list_email_files = glob.glob(email_history_folder_path + '/email_*.email')
    assert len(list_email_files) == 1
