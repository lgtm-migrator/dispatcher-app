import requests

import pytest

def test_construct_for_callback(app):
    from cdci_data_analysis.flask_app.dispatcher_query import InstrumentQueryBackEnd

    query = InstrumentQueryBackEnd(
              app, 
              instrument_name='mock', 
              data_server_call_back=True)

    assert query


@pytest.mark.xfail
def test_callback_without_prior_run_analysis(dispatcher_live_fixture):
    server = dispatcher_live_fixture
    print("constructed server:", server)

    c = requests.get(server + "/call_back",
                   params={},
                )

    print(c.text)

    assert c.status_code == 200

#@app.route('/call_back', methods=['POST', 'GET'])
#def dataserver_call_back():
    #log = logging.getLogger('werkzeug')
    #log.disabled = True
    #app.logger.disabled = True
#    print('===========================> dataserver_call_back')
#    query = InstrumentQueryBackEnd(
#        app, instrument_name='mock', data_server_call_back=True)
#    query.run_call_back()