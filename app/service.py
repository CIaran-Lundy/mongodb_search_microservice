from subprocess import check_output, Popen, PIPE
from pydantic import BaseModel
from typing import Dict, Optional
import requests
import sys
import pymongo


MONGO_HOST = "REMOTE_IP_ADDRESS"
MONGO_DB = "sequencemetadata"
MONGO_USER = "root"
MONGO_PASS = "WGEQPbrbix"


class Input(BaseModel):
    design_id: str
    name: Optional[str] = None
    query: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, list]] = None
    pathway: list


class Service:
    """
    runs the service that is specific to this microservice
    stores the status in status
    """
    def __init__(self, input):
        self.design_id = input.design_id
        self.step = "name2taxid"
        self.status = "running"
        #self.query_key = input.query.keys()[0]
        #self.query_value = input.query.values()[0]

    def get_status_update(self):
        return {"design_id": self.design_id, "step": self.step, "status": self.status}


    def get_query(self, input):
        if input.name is None:
            print(input.query)
            return list(input.query.keys())[0], list(input.query.values())

        client = pymongo.MongoClient('mongodb://mongodb-mongodb-sharded/',
                                     username=MONGO_USER,
                                     password=MONGO_PASS,
                                     authSource='admin',
                                     authMechanism='SCRAM-SHA-256')
        db = client.sequencemetadata
        col = db.accessions

        print(input.name)

        result = col.find_one({'name': input.name})
        print(result)
        if result is None:
            return None
        self.family_taxid = result['family_taxid']
        self.genus_taxid = result['genus_taxid']
        taxid = result['taxid']

        post_item = {'design_id': self.design_id,
                     'taxid': taxid,
                     'pathway': input.pathway}

        response = requests.post("http://lineageservice-service/run/", json=post_item)
        self.taxids = response.json()['taxids']
        self.taxids.append(taxid)

        print("got taxids")

        client.close()

        return 'taxid', self.taxids

    def run(self, input):
        """
        do search against mongodb

        """
        query_key, query_value = self.get_query(input)
        print(query_key, query_value)

        ##Create a MongoDB client

        client = pymongo.MongoClient('mongodb://mongodb-mongodb-sharded/',
                                     username=MONGO_USER,
                                     password=MONGO_PASS,
                                     authSource='admin',
                                     authMechanism='SCRAM-SHA-256')
        db = client.sequencemetadata
        col = db.accessions

        data_dict = {}
        for result in col.find({query_key: {"$in": query_value}}):
            if result['taxid'] not in data_dict.keys():
                data_dict[result['taxid']] = []
            data_dict[result['taxid']].append((result['accession_id'], result['start_byte']))

        client.close()

        self.status = "done"

        if input.name is not None:
            print({"design_id": self.design_id,
                    'data': [data_dict],
                    'metadata': {'taxid': self.taxids,
                                 'family_taxid': [self.family_taxid],
                                 'genus_taxid': [self.genus_taxid],
                                 },
                    'pathway': input.pathway[1:]})
            return {"design_id": self.design_id,
                    'data': [data_dict],
                    'metadata': {'taxid': self.taxids,
                                 'family_taxid': [self.family_taxid],
                                 'genus_taxid': [self.genus_taxid],
                                 },
                    'pathway': input.pathway[1:]}
        else:
            print({"design_id": self.design_id,
                    'data': [data_dict],
                    #'metadata': input.metadata,
                    'pathway': input.pathway[1:]})
            return {"design_id": self.design_id,
                    'data': [data_dict],
                    #'metadata': input.metadata,
                    'pathway': input.pathway[1:]}


if __name__ == "__main__":

    class MyInput2(BaseModel):
        design_id: str = "design.0.0.6.1.1.0.0.0.0.0.0.0"
        query: Optional[Dict[str, str]] = {'family_taxid': '641'}
        name: Optional[str] = None
        pathway: list = ["1", "2"]


    input: MyInput2 = MyInput2()
    service = Service(input)
    output = service.run(input)
    print(output)

    class MyInput(BaseModel):
        design_id: str = "design.0.0.6.1.1.0.0.0.0.0.0.0"
        name: str = "Helicobacter pylori"
        #name: str = "Homo sapiens"
        pathway: list = ["1", "2"]

    input: MyInput = MyInput()
    service = Service(input)
    output = service.run(input)
    print(output)


