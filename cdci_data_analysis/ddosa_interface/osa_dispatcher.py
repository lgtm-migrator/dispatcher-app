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
import  ast

# Dependencies
# eg numpy 
# absolute import eg: import numpy as np
import json

# Project
# relative import eg: from .mod import f

import ddosaclient as dc
from ..analysis.queries import  *
import sys
import traceback


def view_traceback():
    ex_type, ex, tb = sys.exc_info()
    traceback.print_tb(tb)
    del tb


class QueryProduct(object):

    def __init__(self,target=None,modules=[],assume=[],inject=[]):
        self.target=target
        self.modules=modules
        self.assume=assume
        self.inject=inject


class OsaQuery(object):

    def __init__(self,config=None,use_dicosverer=False):

        if use_dicosverer == True:
            try:
                c = discover_docker.DDOSAWorkerContainer()

                self.url = c.url
                self.ddcache_root_local = c.ddcache_root
                print("managed to read from docker:")



            except Exception as e:
                raise RuntimeWarning("failed to read from docker", e)

        elif config is not None:
            try:
                # config=ConfigEnv.from_conf_file(config_file)
                self.url = config.dataserver_url
                self.ddcache_root_local = config.dataserver_cache

            except Exception as e:
                #print(e)

                print ("ERROR->")
                e.display()
                raise RuntimeWarning("failed to use config ", e)

        else:

            raise RuntimeWarning('either you provide use_dicosverer=True or a config object')

        print("url:", self.url)
        print("ddcache_root:",  self.ddcache_root_local)


    def run_query(self,query_prod):

        try:
            res= dc.RemoteDDOSA(self.url, self.ddcache_root_local).query(target=query_prod.target,
                                           modules=query_prod.modules,
                                           assume=query_prod.assume,
                                           inject=query_prod.inject)
            print("cached object in", res,res.ddcache_root_local)
        except dc.WorkerException as e:
            print("ERROR->")
            print('!!! >>>Exception<<<', e)
            view_traceback()

            raise RuntimeWarning('ddosa connection or processing failed',e)

        return res






