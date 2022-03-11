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
sys.path.append("..")
sys.path.append("../app/")


class MyInput(BaseModel):
    design_id: str = "Prototheca-SPP.0.5.5.0.0.0.0.959.0"
    name: Optional[str] = 'test specie'
    query: Optional[Dict[str, str]] = {'test_key': 'test_value'}
    metadata: Optional[Dict[str, list]] = None
    pathway: list = ['this_service', 'next_service']


dummy_database_entry = {'accession_id': 'accession345.1',
                          'start_byte': '12345678',
                          'taxid': '12345',
                          'name': 'test specie',
                          'genus_taxid': '2345',
                          'family_taxid': '345'}


dummy_result = {"design_id": "Prototheca-SPP.0.5.5.0.0.0.0.959.0",
                'data': [('accession345.1', '12345678')],
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


@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
@mock.patch.object(pymongo, 'MongoClient', MyMongoClient)
@pytest.mark.parametrize("input_attr_to_test, input_value, exp_result, exp_taxids, exp_genus_taxid, exp_family_taxid", [
    ('name', None, ('test_key', ['test_value']), None, None, None),
    ('name', "test specie", ('taxid', ['12345']), ['12345'], '2345', '345'),
    ('name', "test SPP", ('taxid', ['12345', '2345']), ['12345', '2345'], '2345', '345'),
    ('name', "nope", None, None, None, None),
  ])
def test_get_query(input_attr_to_test, input_value, exp_result, exp_taxids, exp_family_taxid, exp_genus_taxid):
    input = MyInput()
    setattr(input, input_attr_to_test, input_value)
    service = Service(input)
    setattr(service, 'taxids', None)
    setattr(service, 'genus_taxid', None)
    setattr(service, 'family_taxid', None)
    assert service.get_query(input) == exp_result
    assert service.taxids == exp_taxids
    assert service.family_taxid == exp_family_taxid
    assert service.genus_taxid == exp_genus_taxid
    #assert service.status ==


dummy_result = {"design_id": "Prototheca-SPP.0.5.5.0.0.0.0.959.0",
                'data': [{'12345':[('accession345.1', '12345678')]}],
                'metadata': {'taxid': ['12345'],
                             'family_taxid': ['345'],
                             'genus_taxid': ['2345'],
                             },
                'pathway': ['next_service']}


@mock.patch.object(requests, 'post', mocked_requests_get_for_external_api)
@mock.patch.object(pymongo, 'MongoClient', MyMongoClient)
@pytest.mark.parametrize("query, taxids, genus_taxid, family_taxid, output",
                         [(('taxid', ['12345']), ['12345'], '2345', '345', dummy_result),
                          (('taxid', ['12345']), ['12345'], '2345', '345', dummy_result),
                          (None, None, None, None, None)])
def test_run(query, taxids, genus_taxid, family_taxid, output):
    input = MyInput()
    service = Service(input)
    setattr(service, 'taxids', taxids)
    setattr(service, 'genus_taxid', genus_taxid)
    setattr(service, 'family_taxid', family_taxid)
    with mock.patch.object(Service, 'get_query', return_value=query):
        assert service.run(input) == output




if __name__ == '__main__':
    pytest.main()