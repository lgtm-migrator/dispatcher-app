"""
Overview
--------
   
general info about this module


Classes and Inheritance Structure
----------------------------------------------
.. inheritance-diagram:: 

Summary
---------
.. autosummary::
   list of the module you want
    
Module API
----------
"""

from __future__ import absolute_import, division, print_function

from builtins import (bytes, str, open, super, range,
                      zip, round, input, int, pow, object, map, zip)

__author__ = "Andrea Tramacere"

# Standard library
# eg copy
# absolute import rg:from copy import deepcopy

# Dependencies
# eg numpy 
# absolute import eg: import numpy as np

# Project
# relative import eg: from .mod import f

from cdci_data_analysis.analysis.queries import ProductQuery
from cdci_data_analysis.analysis.products import QueryOutput


class AysnchExcept(Exception):
    pass


class DataServerQuery(ProductQuery):

    def __init__(self, name):
        super(DataServerQuery, self).__init__(name)

    def test_connection(self):
        pass

    def test_has_input_products(self):
        pass

    def get_dummy_products(self, instrument, config=None, **kwargs):
        return []

    def process_product_method(self, instrument, prod_list,api=False, **kw):
        query_out = QueryOutput()
        return query_out

    # example with the general user role
    def check_query_roles(self, roles, par_dic):
        # if use_max_pointings > 50 or scw_list.split(",") > 50:
        #     return 'unige-hpc-full' in roles:
        #
        # return True
        results = dict(authorization=True, needed_roles=[])
        return results


class DataServerNumericQuery(ProductQuery):

    def __init__(self, name, parameters_list=[],):
        super(DataServerNumericQuery, self).__init__(name, parameters_list=parameters_list)

    def test_connection(self):
        pass

    def test_has_input_products(self):
        pass

    def get_dummy_products(self, instrument, config=None, **kwargs):
        return []

    def process_product_method(self, instrument, prod_list, api=False, **kw):
        query_out = QueryOutput()
        return query_out

    # example with the general user role
    def check_query_roles(self, roles, par_dic):
        param_p = self.get_par_by_name('p')
        results = dict(authorization='general' in roles, needed_roles=['general'])
        if 'p' in par_dic.keys():
            # better now, it extracts the value directly from the related parameter object
            p = param_p.value
            if p > 50:
                results['authorization'] = 'general' and 'unige-hpc-full' in roles
                results['needed_roles'] = ['general', 'unige-hpc-full']
        return results

