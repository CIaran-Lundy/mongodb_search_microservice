from subprocess import check_output, Popen, PIPE
from pydantic import BaseModel
from typing import Dict, Optional, Union
import requests
import sys
import pymongo
import bson

MONGO_HOST = "REMOTE_IP_ADDRESS"
MONGO_DB = "sequencemetadata"
MONGO_USER = "youseq"
MONGO_PASS = "Orange01"


class Input(BaseModel):
    design_id: str
    names: Optional[list] = None
    query: Optional[Dict[str, str]] = None
    database: Optional[str] = "sequencemetadata"
    collection: Optional[str] = "accessions"
    metadata: Optional[Dict[str, list]] = None
    pathway: list


def custom_run_decorator(run):
    @wraps(run)
    def _impl(self, *args, **kwargs):
        input = args[0]
        if input.names is None:
            self.query_type = 'custom'
            if input.query is not None:
                return input.query

            else:
                self.status = 'failed'
                self.message = 'query was not valid'
                return None

    return _impl


class Service:
    """
    runs the service that is specific to this microservice
    stores the status in status
    """
    def __init__(self, input):
        self.design_id = input['design_id']
        self.database = input['database']
        self.collection = input['collection']
        self.step = "datafinder"
        self.status = "running"
        self.message = None
        self.query_type = None
        self.__col = self.__get_database_connection()
        self.taxids = [[], [], []]

    def get_status_update(self) -> dict:
        return {"design_id": self.design_id, "step": self.step, "status": self.status, "message": self.message}

    def __get_database_connection(self):
        client = pymongo.MongoClient('mongodb://mongo-nodeport-svc/',
                                     username=MONGO_USER,
                                     password=MONGO_PASS,
                                     authSource='admin',
                                     authMechanism='SCRAM-SHA-256')
        #db = eval(f'{client}.{self.database}')
        db = client.refseq
        col = db.accessions
        #col = eval(f'{db}.{self.collection}')
        return col

    def _process_initial_query(self, name) -> dict:
        """
        takes either:
            --> a custom query
            --> a specie query
            --> an SPP query
        :returns
            --> the custom query in searchable form {key: [value]}
            --> the specie query in searchable form {'name': input.name}
            --> the SPP query in searchable regex form {'name': bson.regex}
        """
        try:
            if 'SPP' in name:
                query = bson.regex.Regex("^" + str(name).split("SPP")[0].strip(' ') + " ")
                self.query_type = 'SPP'
                return {'name': query}

            elif name is not None:
                self.query_type = 'single_specie'
                return {'name': name}
        except:
            self.status = 'failed'
            self.message = 'query was not valid'
            return None

    def _search_initial_query(self, query: dict) -> Union[dict, None]:
        """
        takes:
            --> a searchable query
        returns:
            --> search result
                OR
            --> None and a status update
        """
        result = self.__col.find_one(query)
        if result is None:
            self.status = 'failed'
            self.message = f'{query} not found'
            return None
        return result

    def _get_taxids_from_lineage(self, result: dict):
        """
        takes:
            --> search result
        returns
            --> nothing. (for single_specie or SPP)
                but sets a some instance variables:
                --> taxids
                --> family_taxid
                --> genus_taxid
                OR
                --> None (for custom search)
        """
        if self.query_type == 'single_specie':
            taxid = result['taxid']

        elif self.query_type == 'SPP':
            taxid = result['genus_taxid']

        else:
            return None

        self.taxids[0].append(taxid)

        post_item = {'design_id': self.design_id,
                     'taxid': taxid,
                     'genus_taxid': result['genus_taxid'],
                     'pathway': ['pathway', 'pathway']}

        response = requests.post("http://lineageservice-service/run/", json=post_item)
        # todo: if return code is not 200, set status to message?
        if response.status_code is not 200:
            self.status = 'failed'
            self.message = f'got {response.status_code} from lineageservice'
            return None
        try:
            taxids = response.json()['taxids']

        except KeyError:
            self.status = 'failed'
            self.message = 'lineageservice returned no taxids'
            return None

        for i in range(0,2):
            self.taxids[i].extend(taxids[i])

        try:
            self.family_taxid = result['family_taxid']

        except KeyError:
            self.family_taxid = None

        try:
            self.genus_taxid = result['genus_taxid']

        except KeyError:
            self.genus_taxid = None

        return self.taxids

    def _search_second_query(self, query):
        data_dict = {}
        i = 0
        for result in self.__col.find(query):
            if self.query_type != 'custom':
                if all(key in result.keys() for key in ['accession_id', 'start_byte']):
                    if result['taxid'] not in data_dict.keys():
                        data_dict[result['taxid']] = []
                    data_dict[result['taxid']].append((result['accession_id'], result['start_byte']))
            else:
                data_dict[i] = result
                i += 1
        return data_dict

    def _create_query_from_names(self, input: Input) -> Union[dict, None]:

        for name in input['names']:
            initial_query = self._process_initial_query(name)
            print(f'query_type: {self.query_type}')
            print(f'initial_query: {initial_query}')
            if initial_query is None:
                self.message = 'initial search result was None'
                print(self.status)
                return None

            initial_search_result = self._search_initial_query(initial_query)
            print(f'initial_search_result: {initial_search_result}')
            if initial_search_result is None:
                print(self.status)
                return None

            if self.query_type in ('SPP', 'single_specie'):
                taxids = self._get_taxids_from_lineage(initial_search_result)
                print(f'taxids: {taxids}')
                if taxids is None:
                    print(self.status)
                    return None

        return {'taxid': {"$in": self.taxids[0] + self.taxids[1]}}

    def run(self, input) -> dict:

        if input['names'] is None:
            self.query_type = 'custom'
            if input['query'] is None:
                self.status = 'failed'
                self.message = 'query was not valid'
                return None

        else:
            input['query'] = self._create_query_from_names(input)
            if input['query'] is None:
                return None

        #second_query = self._process_second_query(input.query)
        #print(f'second_query: {second_query}')
        #if second_query is None:
        #    print(self.status)
        #    return None
        print(f'second_search_query: {input["query"]}')
        second_search_result = self._search_second_query(input['query'])
        print(f'second_search_result: {second_search_result}')
        if second_search_result is None:
            print(self.status)
            return None

        if input['names'] is not None:
            output = {"design_id": self.design_id,
                    'data': [second_search_result],
                    'metadata': {'taxid': self.taxids,
                                 'family_taxid': [self.family_taxid],
                                 'genus_taxid': [self.genus_taxid],
                                 },
                    'pathway': input['pathway'][1:]}

        else:
            output = {"design_id": self.design_id,
                      'data': [second_search_result],
                      'pathway': input['pathway'][1:]}
        print(output)
        self.status = 'done'
        return [output]

    #def get_query(self, input):
    #    """
    #    this service can take a few different types of query:
    #    --> Genus + specie type query
    #    --> Genus + SPP type query
    #    --> custom query
    #    this returns a search query that searches for an appropriate taxid for the first 2 query types
    #    or just the input custom search query for the third type of query

    #    IT ALSO SETS SOME CLASS VARIABLES like self.taxids, self.family_taxid and self.genus_taxid
    #    """
    #    if input.name is None:
    #        print(input.query)
    #        print('custom query')
    #        return list(input.query.keys())[0], list(input.query.values())#

    #    client = pymongo.MongoClient('mongodb://mongo-nodeport-svc/',
    #                                 username=MONGO_USER,
    #                                 password=MONGO_PASS,
    #                                 authSource='admin',
    #                                 authMechanism='SCRAM-SHA-256')
    #    db = client.sequencemetadata
    #     col = db.accessions
    #
    #     print(input.name)
    #     self.SPP = False
    #     if 'SPP' in input.name:
    #         input.name = bson.regex.Regex("^" + str(input.name).split(" ")[0] + " ")
    #         print(input.name)
    #         self.SPP = True
    #     result = col.find_one({'name': input.name})
    #     print(result)
    #     if result is None:
    #         print("no results found")
    #         self.status = f'failed - {input.name} not found'
    #         return None
    #     print(result)
    #     self.family_taxid = result['family_taxid']
    #     self.genus_taxid = result['genus_taxid']
    #     taxid = result['taxid']
    #
    #     if self.SPP:
    #         taxid = self.genus_taxid
    #
    #     post_item = {'design_id': self.design_id,
    #                  'taxid': taxid,
    #                  'pathway': input.pathway}
    #
    #     response = requests.post("http://lineageservice-service/run/", json=post_item)
    #     self.taxids = response.json()['taxids']
    #     self.taxids.append(taxid)
    #
    #     print("got taxids")
    #
    #     client.close()
    #
    #     return 'taxid', self.taxids
    #
    # def run(self, input):
    #     """
    #     do search against mongodb
    #     """
    #     try:
    #         query_key, query_value = self.get_query(input)
    #         print(query_key, query_value)
    #     except:
    #         return None
    #
    #
    #     ##Create a MongoDB client
    #
    #     client = pymongo.MongoClient('mongodb://mongo-nodeport-svc/',
    #                                  username=MONGO_USER,
    #                                  password=MONGO_PASS,
    #                                  authSource='admin',
    #                                  authMechanism='SCRAM-SHA-256')
    #     db = client.sequencemetadata
    #     col = db.accessions
    #
    #     data_dict = {}
    #     for result in col.find({query_key: {"$in": query_value}}):
    #         if result['taxid'] not in data_dict.keys():
    #             data_dict[result['taxid']] = []
    #         data_dict[result['taxid']].append((result['accession_id'], result['start_byte']))
    #
    #     client.close()
    #
    #     self.status = "done"
    #
    #     if input.name is not None:
    #         print({"design_id": self.design_id,
    #                 'data': [data_dict],
    #                 'metadata': {'taxid': self.taxids,
    #                              'family_taxid': [self.family_taxid],
    #                              'genus_taxid': [self.genus_taxid],
    #                              },
    #                 'pathway': input.pathway[1:]})
    #         return {"design_id": self.design_id,
    #                 'data': [data_dict],
    #                 'metadata': {'taxid': self.taxids,
    #                              'family_taxid': [self.family_taxid],
    #                              'genus_taxid': [self.genus_taxid],
    #                              },
    #                 'pathway': input.pathway[1:]}
    #     else:
    #         print({"design_id": self.design_id,
    #                 'data': [data_dict],
    #                 #'metadata': input.metadata,
    #                 'pathway': input.pathway[1:]})
    #         return {"design_id": self.design_id,
    #                 'data': [data_dict],
    #                 #'metadata': input.metadata,
    #                 'pathway': input.pathway[1:]}


if __name__ == "__main__":

    input = {
            "design_id": "design.0.0.6.1.1.0.0.0.0.0.0.0",
            "names": None,
            "query": {'taxid': '1352'},
            "database":  "refseq",
            "collection": "accessions",
            "metadata":  None,
            "pathway": [1,2]
            }

    service = Service(input)
    output = service.run(input)
    print(output)

