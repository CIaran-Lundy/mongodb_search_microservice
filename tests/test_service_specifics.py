import zlib
import sys
from subprocess import check_output, Popen, PIPE
from pydantic import BaseModel
from typing import Dict
import pytest
#import pytest_mock
#from mock import Mock
import mock
import sys
from app.service import Service

sys.path.append("..")
sys.path.append("../app/")


class MyInput(BaseModel):
    design_id: str = "Prototheca-SPP.0.5.5.0.0.0.0.959.0"
    data: str = "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT"
    metadata: Dict[str, list] = {'taxid': ['3110']}
    pathway: list = ['this_service', 'next_service']


@pytest.mark.parametrize("input_attribute_to_test, input_value, output_key_to_test, expected_result", [
    ('data', "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT", 'data', ["TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT"]),
    ('data', "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT", "priority", 0),
    ('data', "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT", "priority", 0),
    ('data', "TTTTTTTTTTTTTTTTTTTTTTTTTT", "priority", 0),
    ('data', "", "priority", 0),
    ('data', "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGA", "priority", 0),
    ('data', "atcctctttaaaataagcatatcctctttaaaataagcatatcctctttaaaataagcatatcctctttaaaataagcat", "priority", 0),
    ('data', "atcctctttaaaataagcatttgtaggatctacatagtagtatgttccatcaatctgaaccagattccatgcatgtcgaattctattact", "priority", 1),
    ('data', "atcctctttaaaataagcatttgtaggatctacatagtagtatgttccatcaatctgaaccagattccatgcatgtcgaattctattactNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN", "priority", 1),
    ('data', "atcctctttaaaataagcatttgtaggatctacatagtagtatgttccatcaatctgaaccagattccatgcatgtcgaattctattactatcctctttaaaataagcatttgtaggatctacatagtagtatgttccatcaatctgaac", "priority", 2),
])
def test_run(input_attribute_to_test, input_value, output_key_to_test, expected_result):
    input = MyInput()
    setattr(input, input_attribute_to_test, input_value)
    service = Service(input)
    assert service.run(input)[output_key_to_test] == expected_result


if __name__ == '__main__':
    pytest.main()