import zlib
import sys
from subprocess import check_output, Popen, PIPE
from pydantic import BaseModel
from typing import Dict, Optional
import pytest
#import pytest_mock
#from mock import Mock
import mock
import sys
import mongomock
import pymongo
import requests
from app.service import Service
from bson.regex import Regex as Regex
sys.path.append("..")
sys.path.append("../app/")


class MyInput(BaseModel):
    design_id: str = "Prototheca-SPP.0.5.5.0.0.0.0.959.0"
    name: Optional[str] = None
    query: Optional[Dict[str, str]] = {'family_taxid': '345'}
    metadata: Optional[Dict[str, list]] = None
    pathway: list = ['this_service', 'next_service']


dummy_database_entries = [{'accession_id': 'accession345.1',
                          'start_byte': '12345678',
                          'taxid': '12345',
                          'name': 'test specie',
                          'genus_taxid': '2345',
                          'family_taxid': '345'},
                          {'accession_id': 'accession789.1',
                           'start_byte': '789',
                           'taxid': '56789',
                           'name': 'test specie2',
                           'family_taxid': '789'},
                          {'accession_id': 'accession789.1',
                           'start_byte': '789',
                           'taxid': '5678',
                           'name': 'test specie3',
                           'genus_taxid': '6789'},
                          {'accession_id': 'accession789.1',
                           'start_byte': '789',
                           'taxid': '5678',
                           'name': 'test specie4',
                           'genus_taxid': '6789',
                           'family_taxid': '789'},
                          ]


dummy_result = {"design_id": "Prototheca-SPP.0.5.5.0.0.0.0.959.0",
                'data': [{'12345':[('accession345.1', '12345678')]}],
                'metadata': {'taxid': ['12345'],
                             'family_taxid': ['345'],
                             'genus_taxid': ['2345'],
                             },
                'pathway': ['next_service']}


class MyMongoClient:
    def __init__(self, *args, **kwargs):
        pass
    class sequencemetadata:
        def __init__(self, *args):
            pass

        accessions = mongomock.MongoClient().db.collection
        for dummy_database_entry in dummy_database_entries:
            accessions.insert_one(dummy_database_entry)

    def close(self):
        pass


def mocked_requests_get_for_external_api(*args, **kwargs):
    class MockResponse:
        def __init__(self, content, status_code, json):
            self.content = content
            self.status_code = status_code
            if json['taxid'] == '2345':
                self.json_data = {'taxids': ['12345']}
            else:
                self.json_data = {'taxids': []}

        def json(self):
            return self.json_data

    json = kwargs['json']

    return MockResponse(str('content'), 200, json)


@pytest.mark.parametrize("input_attr_to_test, input_value, exp_result, exp_query_type, status",  [
    ('name', None, {'family_taxid': '345'}, 'custom', "running"),
    ('name', "test specie", {'name': "test specie"}, 'single_specie', "running"),
    ('name', "test SPP", {'name': Regex('^test ', 0)}, 'SPP', "running"),
    ('name', "nope", {'name': "nope"}, 'single_specie', "running"),
    ('query', None, None, 'custom', 'failed - query was not valid'),
  ])
def test_process_initial_query(input_attr_to_test, input_value, exp_result, exp_query_type, status):
    input = MyInput()
    setattr(input, input_attr_to_test, input_value)
    service = Service(input)
    assert service._process_initial_query(input) == exp_result
    assert service.query_type == exp_query_type
    assert service.status == status


@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
@mock.patch.object(pymongo, 'MongoClient', MyMongoClient)
@pytest.mark.parametrize("query, exp_result, exp_status", [
    ({'family_taxid': '345'}, dummy_database_entries[0], "running"),
    ({'name': Regex('^test ', 0)}, dummy_database_entries[0], 'running'),
    ({'name': "test specie"}, dummy_database_entries[0], 'running'),
    ({'name': "nope"}, None, "failed - {'name': 'nope'} not found"),
    ({'family_taxid': '3'}, None, "failed - {'family_taxid': '3'} not found"),
    ({'name': Regex('^wrong ', 0)}, None, "failed - {'name': Regex('^wrong ', 0)} not found"),
  ])
def test_search_initial_query(query, exp_result, exp_status):
    input = MyInput()
    service = Service(input)
    assert service._search_initial_query(query) == exp_result
    assert service.status == exp_status


@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
@pytest.mark.parametrize("query_type, search_result, exp_taxids, exp_genus_taxid, exp_family_taxid", [
    ('single_specie', dummy_database_entries[0], ['12345'], '2345', '345'),
    ('SPP', dummy_database_entries[0], ['12345', '2345'], '2345', '345'),
    ('custom', dummy_database_entries[0], None, None, None),
    ('single_specie', dummy_database_entries[1], ['56789'], None, '789'),
  ])
def test_get_taxids_from_lineage(query_type, search_result, exp_taxids, exp_genus_taxid, exp_family_taxid):
    input = MyInput()
    service = Service(input)
    setattr(service, 'taxids', None)
    setattr(service, 'genus_taxid', None)
    setattr(service, 'family_taxid', None)
    setattr(service, "query_type", query_type)
    service._get_taxids_from_lineage(search_result)
    assert service.taxids == exp_taxids
    assert service.genus_taxid == exp_genus_taxid
    assert service.family_taxid == exp_family_taxid


@pytest.mark.parametrize("input_attr_to_test, input_value, query_type, exp_result", [
    ('name', None, 'custom', {'family_taxid': '345'}),
    ('taxids', ['12345'], 'single_specie', {'taxid': {"$in": ['12345']}}),
    ('taxids', ['12345', '2345'], 'SPP', {'taxid': {"$in": ['12345', '2345']}}),
    ('name', "nope", 'custom', {'family_taxid': '345'}),
  ])
def test_process_second_query(input_attr_to_test, input_value, query_type, exp_result):
    input = MyInput()
    service = Service(input)
    setattr(service, input_attr_to_test, input_value)
    setattr(service, "query_type", query_type)
    assert service._process_second_query(input) == exp_result


@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
@mock.patch.object(pymongo, 'MongoClient', MyMongoClient)
@pytest.mark.parametrize("query, exp_result, exp_status", [
    ({'taxid': {"$in": ['12345']}}, {'12345': [('accession345.1', '12345678')]}, "running"),
    ({'taxid': {"$in": ['12345', '2345']}}, {'12345': [('accession345.1','12345678')]}, 'running'),
  ])
def test_search_second_query(query, exp_result, exp_status):
    input = MyInput()
    service = Service(input)
    assert service._search_second_query(query) == exp_result
    assert service.status == exp_status

@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
@mock.patch.object(pymongo, 'MongoClient', MyMongoClient)
@pytest.mark.parametrize("input_attr_to_test, input_value, exp_result, exp_query_type, status",  [
    ('name', None, {"design_id": "Prototheca-SPP.0.5.5.0.0.0.0.959.0",
                'data': [{'12345': [('accession345.1', '12345678')]}],
                'pathway': ['next_service']}, 'custom', "running"),
    ('name', "test specie", {"design_id": "Prototheca-SPP.0.5.5.0.0.0.0.959.0",
                'data': [{'12345':[('accession345.1', '12345678')]}],
                'metadata': {'taxid': ['12345'],
                             'family_taxid': ['345'],
                             'genus_taxid': ['2345'],
                             },
                'pathway': ['next_service']}, 'single_specie', "done"),
    ('name', "test SPP", {"design_id": "Prototheca-SPP.0.5.5.0.0.0.0.959.0",
                'data': [{'12345':[('accession345.1', '12345678')]}],
                'metadata': {'taxid': ['12345', '2345'],
                             'family_taxid': ['345'],
                             'genus_taxid': ['2345'],
                             },
                'pathway': ['next_service']}, 'SPP', "done"),
    ('name', "test", None, 'single_specie', "failed - {'name': 'test'} not found"),
    #('name', "nope", {'name': "nope"}, 'single_specie', "running"),
    #('query', None, None, 'custom', 'failed - query was not valid'),
  ])
def test_run2(input_attr_to_test, input_value, exp_result, exp_query_type, status):
    input = MyInput()
    setattr(input, input_attr_to_test, input_value)
    service = Service(input)
    assert service.run(input) == exp_result
    assert service.query_type == exp_query_type


#@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
#@mock.patch.object(pymongo, 'MongoClient', MyMongoClient)
#@pytest.mark.parametrize("input_attr_to_test, input_value, exp_result, exp_taxids, exp_genus_taxid, exp_family_taxid", [
#    ('name', None, ('test_key', ['test_value']), None, None, None),
#    ('name', "test specie", ('taxid', ['12345']), ['12345'], '2345', '345'),
#    ('name', "test SPP", ('taxid', ['12345', '2345']), ['12345', '2345'], '2345', '345'),
#    ('name', "nope", None, None, None, None),
#  ])
#def test_get_query(input_attr_to_test, input_value, exp_result, exp_taxids, exp_family_taxid, exp_genus_taxid):
#    input = MyInput()
#    setattr(input, input_attr_to_test, input_value)
#    service = Service(input)
#    setattr(service, 'taxids', None)
#    setattr(service, 'genus_taxid', None)
#    setattr(service, 'family_taxid', None)
#    assert service.get_query(input) == exp_result
#    assert service.taxids == exp_taxids
#    assert service.family_taxid == exp_family_taxid
#    assert service.genus_taxid == exp_genus_taxid


dummy_result = {"design_id": "Prototheca-SPP.0.5.5.0.0.0.0.959.0",
                'data': [{'12345':[('accession345.1', '12345678')]}],
                'metadata': {'taxid': ['12345'],
                             'family_taxid': ['345'],
                             'genus_taxid': ['2345'],
                             },
                'pathway': ['next_service']}


#@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
#@mock.patch.object(pymongo, 'MongoClient', MyMongoClient)
#@pytest.mark.parametrize("query, taxids, genus_taxid, family_taxid, output",
#                         [(('taxid', ['12345']), ['12345'], '2345', '345', dummy_result),
#                          (('taxid', ['12345']), ['12345'], '2345', '345', dummy_result),
#                          (None, None, None, None, None)])
#def test_run(query, taxids, genus_taxid, family_taxid, output):
#    input = MyInput()
#    service = Service(input)
#    setattr(service, 'taxids', taxids)
#    setattr(service, 'genus_taxid', genus_taxid)
#    setattr(service, 'family_taxid', family_taxid)
#    with mock.patch.object(Service, 'get_query', return_value=query):
#        assert service.run(input) == output


if __name__ == '__main__':
    pytest.main()