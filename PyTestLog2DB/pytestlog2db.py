#  Copyright 2020-2022 Robert Bosch Car Multimedia GmbH
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# *******************************************************************************
#
# File: pytestlog2db.py
#
# Initialy created by Tran Duy Ngoan(RBVH/ECM11) / November 2022
#lxml
# This tool is used to parse the pytest JUnit XML report file(s)
# then import them into TestResultWebApp's database
#  
# History:
# 
# 2022-11-22:
#  - initial version
#
# *******************************************************************************

import re
import uuid
import base64
import argparse
import os
import sys
import colorama as col
import json
from lxml import etree
from datetime import datetime, timedelta
import platform 
from pkg_resources import get_distribution
import pytest

from PyTestLog2DB.CDataBase import CDataBase
from PyTestLog2DB.version import VERSION, VERSION_DATE

PYTEST_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DB_STR_FIELD_MAXLENGTH = {
   "project" : 20,
   "variant" : 20,
   "branch"  : 20,
   "version_sw_target" : 100,
   "version_sw_test" : 100,
   "version_hardware" : 100,
   "jenkinsurl" : 255,
   "reporting_qualitygate" : 45,
   "name" : 255,
   "tester_account" : 100,
   "tester_machine" : 45,
   "origin" : 45,
   "testtoolconfiguration_testtoolname" : 45,
   "testtoolconfiguration_testtoolversionstring" : 255,
   "testtoolconfiguration_projectname" : 255,
   "testtoolconfiguration_logfileencoding" : 45,
   "testtoolconfiguration_pythonversion" : 255,
   "testtoolconfiguration_testfile" : 255,
   "testtoolconfiguration_logfilepath" : 255,
   "testtoolconfiguration_logfilemode" : 45,
   "testtoolconfiguration_ctrlfilepath" : 255,
   "testtoolconfiguration_configfile" : 255,
   "testtoolconfiguration_confname" : 255,
   "testfileheader_author" : 255,
   "testfileheader_project" : 255,
   "testfileheader_testfiledate" : 255,
   "testfileheader_version_major" : 45,
   "testfileheader_version_minor" : 45,
   "testfileheader_version_patch" : 45,
   "testfileheader_keyword" : 255,
   "testfileheader_shortdescription" : 255,
   "testexecution_useraccount" : 255,
   "testexecution_computername" : 255,
   "testrequirements_documentmanagement" : 255,
   "testrequirements_testenvironment" : 255,
   "testbenchconfig_name" : 255,
   "preprocessor_filter" : 45,
   "issue" : 50,
   "tcid" : 50,
   "fid" : 255,
   "component" : 45
}

def __current_user():
   """
Get current executing user.\
This information is used as default value for `tester` when importing.

**Arguments:**

(*no arguments*)

**Returns:**

*  ``sUserName`` 

   / *Type*: str /

   User name of current user.
   """

   sUserName=""
   # allow windows system access only in windows systems
   if platform.system().lower()!="windows":
      try:
         sUserName=os.getenv("USER","")
      except Exception as reason:
         pass
   else:
      import ctypes
      try:
         GetUserNameEx = ctypes.windll.secur32.GetUserNameExW
         NameDisplay = 3
      
         size = ctypes.pointer(ctypes.c_ulong(0))
         GetUserNameEx(NameDisplay, None, size)
         
         nameBuffer = ctypes.create_unicode_buffer(size.contents.value)
         GetUserNameEx(NameDisplay, nameBuffer, size)
         
         sUserName=nameBuffer.value
      except:
         pass
      
   return sUserName

def __curent_testtool():
   """
Get current versions of Python and PyTest.\
This information is used as default value for `testtool` when importing.

**Arguments:**

(*no arguments*)

**Returns:**

   / *Type*: str /

   Current PyTest and Python verions as testtool.\
   E.g: PyTest 6.2.5 (Python 3.9.0)
   """
   return f"PyTest {get_distribution('pytest').version} (Python {platform.python_version()})"

CONFIG_SCHEMA = {
   "components" : [str, dict],
   "variant"   : str,
   "version_sw": str,
   "version_hw": str,
   "version_test": str,
   "testtool"  :  str,
   "tester"    :  str
}

DEFAULT_METADATA = {
   "components"   :  "unknown",
   "variant"      :  "PyTest",
   "version_sw"   :  "",
   "version_hw"   :  "",
   "version_test" :  "",
   "testtool"     :  __curent_testtool(),
   "tester"       :  __current_user()
}

class Logger():
   """
Logger class for logging message.
   """
   output_logfile = None
   output_console = True
   color_normal   = col.Fore.WHITE + col.Style.NORMAL
   color_error    = col.Fore.RED + col.Style.BRIGHT
   color_warn     = col.Fore.YELLOW + col.Style.BRIGHT
   color_reset    = col.Style.RESET_ALL + col.Fore.RESET + col.Back.RESET
   prefix_warn    = "WARN: "
   prefix_error   = "ERROR: "
   prefix_fatalerror = "FATAL ERROR: "
   prefix_all = ""
   dryrun = False

   @classmethod
   def config(cls, output_console=True, output_logfile=None, indent=0, dryrun=False):
      """
Configure Logger class.

**Arguments:**

*  ``output_console``

   / *Condition*: optional / *Type*: bool / *Default*: True /

   Write message to console output.

*  ``output_logfile``

   / *Condition*: optional / *Type*: str / *Default*: None /

   Path to log file output.

*  ``indent``

   / *Condition*: optional / *Type*: int / *Default*: 0 /

   Offset indent.

*  ``dryrun``

   / *Condition*: optional / *Type*: bool / *Default*: True /

   If set, a prefix as 'dryrun' is added for all messages.

**Returns:**

(*no returns*)
      """
      cls.output_console = output_console
      cls.output_logfile = output_logfile
      cls.dryrun = dryrun
      if cls.dryrun:
         cls.prefix_all = cls.color_warn + "DRYRUN  " + cls.color_reset

   @classmethod
   def log(cls, msg="", color=None, indent=0):
      """
Write log message to console/file output.

**Arguments:**

*  ``msg``

   / *Condition*: optional / *Type*: str / *Default*: "" /

   Message which is written to output.

*  ``color``

   / *Condition*: optional / *Type*: str / *Default*: None /

   Color style for the message.

*  ``indent``

   / *Condition*: optional / *Type*: int / *Default*: 0 /

   Offset indent.
      
**Returns:**

(*no returns*)
      """
      if color==None:
         color = cls.color_normal
      if cls.output_console:
         print(cls.prefix_all + cls.color_reset + color + " "*indent + msg + cls.color_reset)
      if cls.output_logfile!=None and os.path.isfile(cls.output_logfile):
         with open(cls.output_logfile, "a") as f:
            f.write(" "*indent + msg)
      return

   @classmethod
   def log_warning(cls, msg):
      """
Write warning message to console/file output.
      
**Arguments:**

*  ``msg``

   / *Condition*: required / *Type*: str /

   Warning message which is written to output.

**Returns:**

(*no returns*)
      """
      cls.log(cls.prefix_warn+str(msg), cls.color_warn)

   @classmethod
   def log_error(cls, msg, fatal_error=False):
      """
Write error message to console/file output.

**Arguments:**

*  ``msg``

   / *Condition*: required / *Type*: str /

   Error message which is written to output.

*  ``fatal_error``

   / *Condition*: optional / *Type*: bool / *Default*: False /

   If set, tool will terminate after logging error message.

**Returns:**

(*no returns*)
      """
      prefix = cls.prefix_error
      if fatal_error:
         prefix = cls.prefix_fatalerror

      cls.log(prefix+str(msg), cls.color_error)
      if fatal_error:
         cls.log("%s has been stopped!"%(sys.argv[0]), cls.color_error)
         exit(1)

def __process_commandline():
   """
Process provided argument(s) from command line.

Avalable arguments in command line:

   - `-v` : tool version information.
   - `resultxmlfile` : path to the xml pytest result file or directory of result files to be imported.
   - `server` : server which hosts the database (IP or URL).
   - `user` : user for database login.
   - `password` : password for database login.
   - `database` : database name.
   - `--recursive` : if True, then the path is searched recursively for *.xml files to be imported.
   - `--dryrun` : if True, then verify all input arguments (includes DB connection) and show what would be done.
   - `--append` : if True, then allow to append new result(s) to existing execution result UUID which is provided by -UUID argument.
   - `--UUID` : UUID used to identify the import and version ID on TestResultWebApp.
   - `--config` : configuration json file for component mapping information.

**Arguments:**

(*no arguments*)

**Returns:**

   / *Type*: `ArgumentParser` object /

   ArgumentParser object.
   """
   cmdlineparser=argparse.ArgumentParser(prog="PyTestLog2DB (PyTestXMLReport to TestResultWebApp importer)", 
                                         description="PyTestLog2DB imports pytest JUnit XML report file(s)" + \
                                                     "generated by pytest into a WebApp database."
                                        )

   cmdlineparser.add_argument('-v',action='version', version=f'v{VERSION} ({VERSION_DATE})',help='Version of the PyTestLog2DB importer.')
   cmdlineparser.add_argument('resultxmlfile', type=str, help='absolute or relative path to the pytest JUnit XML report file or directory of report files to be imported.')
   cmdlineparser.add_argument('server', type=str, help='server which hosts the database (IP or URL).')
   cmdlineparser.add_argument('user', type=str, help='user for database login.')
   cmdlineparser.add_argument('password', type=str, help='password for database login.')
   cmdlineparser.add_argument('database', type=str, help='database schema for database login.')
   cmdlineparser.add_argument('--recursive', action="store_true", help='if set, then the path is searched recursively for output files to be imported.')
   cmdlineparser.add_argument('--dryrun', action="store_true", help='if set, then verify all input arguments (includes DB connection) and show what would be done.')
   cmdlineparser.add_argument('--append', action="store_true", help='is used in combination with -UUID <UUID>.' +\
                              ' If set, allow to append new result(s) to existing execution result UUID in -UUID argument.')
   cmdlineparser.add_argument('--UUID', type=str, help='UUID used to identify the import and version ID on webapp.' + \
                              ' If not provided PyTestLog2DB will generate an UUID for the whole import.')
   cmdlineparser.add_argument('--config', type=str, help='configuration json file for component mapping information.')

   return cmdlineparser.parse_args()

def is_valid_uuid(uuid_to_test, version=4):
   """
Verify the given UUID is valid or not.

**Arguments:**

*  ``uuid_to_test``

   / *Condition*: required / *Type*: str /
   
   UUID to be verified.

*  ``version``

   / *Condition*: optional / *Type*: int / *Default*: 4 /
   
   UUID version.

**Returns:**

*  ``bValid``

   / *Type*: bool /

   True if the given UUID is valid.
   """
   bValid = False
   try:
      uuid_obj = uuid.UUID(uuid_to_test, version=version)
   except:
      return bValid
   
   if str(uuid_obj) == uuid_to_test:
      bValid = True
   
   return bValid

def is_valid_config(dConfig, dSchema=CONFIG_SCHEMA, bExitOnFail=True):
   """
Validate the json configuration base on given schema.

Default schema supports below information:

.. code:: python

   CONFIG_SCHEMA = {
      "components": [str, dict],
      "variant"   : str,
      "version_sw": str,
      "version_hw": str,
      "version_test": str,
      "testtool"  :  str,
      "tester"    :  str
   }

**Arguments:**

*  ``dConfig``

   / *Condition*: required / *Type*: dict /

   Json configuration object to be verified.

*  ``dSchema``

   / *Condition*: optional / *Type*: dict / *Default*: CONFIG_SCHEMA /

   Schema for the validation.

*  ``bExitOnFail``

   / *Condition*: optional / *Type*: bool / *Default*: True /

   If True, exit tool in case the validation is fail.

**Returns:**

*  ``bValid``

   / *Type*: bool /

   True if the given json configuration data is valid.
   """
   bValid = True
   for key in dConfig:
      if key in dSchema.keys():
         # List of support types
         if isinstance(dSchema[key], list):
            if type(dConfig[key]) not in dSchema[key]:
               bValid = False
         # Fixed type
         else:
            if type(dConfig[key]) != dSchema[key]:
               bValid = False

         if not bValid:
            Logger.log_error("Value of '%s' has wrong type '%s' in configuration json file."%(key,type(dSchema[key])), fatal_error=bExitOnFail)

      else:
         bValid = False
         Logger.log_error("Invalid key '%s' in configuration json file."%key, fatal_error=bExitOnFail)
   
   return bValid

def validate_db_str_field(field, value):
   """
Validate the string value for database field bases on its acceptable length.\
The error will be thrown and tool terminates if the verification is failed.

**Arguments:**

*  ``field``

   / *Condition*: required / *Type*: str /

   Field name in the database.

*  ``value``

   / *Condition*: required / *Type*: str /

   String value to be verified.

**Returns:**

   / *Type*: str /

   String value if the verification is fine.
   """
   if field in DB_STR_FIELD_MAXLENGTH:
      if len(value) > DB_STR_FIELD_MAXLENGTH[field]:
         Logger.log_error(f"Provided value '{value}' for '{field}' is longer than acceptable {DB_STR_FIELD_MAXLENGTH[field]} chars.", fatal_error=True)
      else:
         return value
   else:
      Logger.log_error(f"Invalid field '{field}' to import into database", fatal_error=True)

def truncate_db_str_field(sString, iMaxLength, sEndChars="..."):
   """
Truncate input string before importing to database.

**Arguments:**

*  ``sString``

   / *Condition*: required / *Type*: str /

   Input string for truncation.

*  ``iMaxLength``

   / *Condition*: required / *Type*: int /

   Max length of string to be allowed. 

*  ``sEndChars``

   / *Condition*: optional / *Type*: str / *Default*: "..." /

   End characters which are added to end of truncated string.

**Returns:**

*  ``content``

   / *Type*: str /

   String after truncation.
   """
   content = str(sString)
   if isinstance(iMaxLength, int):
      if len(content) > iMaxLength:
         content = content[:iMaxLength-len(sEndChars)] + sEndChars
   else:
      raise Exception("parameter iMaxLength should be an integer")
   
   return content

def parse_pytest_xml(*xmlfiles):
   """
Parse and merge all given pytest *.xml result files into one result file.\
Besides, `starttime` and `endtime` are also calculated and added in the merged result.

**Arguments:**

*  ``xmlfiles``

   / *Condition*: required / *Type*: str /

   Path to pytest *.xml result file(s).

**Returns:**

*  ``oMergedTree``

   / *Type*: `etree._Element` object /

   The result object which is parsed from provided pytest *.xml result file(s).
   """
   oMergedTree = None
   dtStartTime = None
   dtEndTime   = None

   try:
      for item in xmlfiles:
         oTree = etree.parse(item).getroot()
         if oMergedTree == None:
            oMergedTree = oTree
            sStartTime  = oMergedTree.getchildren()[0].get("timestamp")
            dtStartTime = datetime.strptime(sStartTime, PYTEST_DATETIME_FORMAT)
            dtEndTime   = dtStartTime + timedelta(seconds=float(oMergedTree.getchildren()[0].get("time")))
         else:
            oAdditionalTree = etree.parse(item)
            for oSuite in oAdditionalTree.getroot().iterchildren("testsuite"):
               oMergedTree.append(oSuite)
               dtTimestamp = datetime.strptime(oSuite.get("timestamp"), PYTEST_DATETIME_FORMAT)

               # check starttime and endtime for the execution result
               if dtTimestamp < dtStartTime:
                  dtStartTime = dtTimestamp
               elif (dtTimestamp + timedelta(seconds=float(oSuite.get("time"))))> dtEndTime:
                  dtEndTime = dtTimestamp

   except Exception as reason:
      Logger.log_error(f"Error when merging pytest xml files. Reason: {reason}", fatal_error=True)
   
   # Additional attributes for testsuites
   oMergedTree.attrib["starttime"] = datetime.strftime(dtStartTime, DB_DATETIME_FORMAT)
   oMergedTree.attrib["endtime"] = datetime.strftime(dtEndTime, DB_DATETIME_FORMAT)

   return oMergedTree

def get_branch_from_swversion(sw_version):
   """
Get branch name from software version information.

Convention of branch information in suffix of software version:

*  All software version with .0F is the main/freature branch. 
   The leading number is the current year. E.g. ``17.0F03``
*  All software version with ``.1S``, ``.2S``, ... is a stabi branch. 
   The leading number is the year of branching out for stabilization.
   The number before "S" is the order of branching out in the year.
   
**Arguments:**

*  ``sw_version``

   / *Condition*: required / *Type*: str /
   
   Software version.

**Returns:**

*  ``branch_name``

   / *Type*: str /

   Branch name.
   """
   branch_name = "main"
   version_number=re.findall("(\d+\.)(\d+)([S,F])\d+",sw_version.upper())
   try:
      branch_name = "".join(version_number[0])
   except:
      pass
   if branch_name.endswith(".0F"):
      branch_name="main"
   return branch_name

def get_test_result(oTest):
   """
Get test result from provided Testcase object.

**Arguments:**

*  ``oTest``

   / *Condition*: required / *Type*: `etree._Element` object /

   Testcase object.

**Returns:**

   / *Type*: typle /

   Testcase result which contains `result_main`, `lastlog` and `result_return`.
   """
   main_result = "Passed"
   traceback_log = ""
   return_code = 11
   if failure := list(oTest.iterchildren("failure")):
      main_result = "Failed"
      traceback_log = f"{failure[0].get('message')}\n{failure[0].text}"
      return_code = 12
   elif error := list(oTest.iterchildren("error")):
      main_result = "unknown"
      traceback_log = f"{error[0].get('message')}\n{error[0].text}"
      return_code = 5
   elif list(oTest.iterchildren("skipped")):
      main_result = "unknown"
      traceback_log = f"This test is skipped."
      return_code = 20

   return (main_result, base64.b64encode(traceback_log.encode()), return_code)

def process_component_info(dConfig, sTestClassname):
   """
Return the component name bases on provided testcase's classname and component
mapping.

**Arguments:**

*  ``dConfig``

   / *Condition*: required / *Type*: dict /

   Configuration which contains the mapping between component and testcase's classname.

*  ``sTestClassname``

   / *Condition*: required / *Type*: str /

   Testcase's classname to get the component info.

**Returns:**

*  ``sComponent``

   / *Type*: typle /

   Component name maps with given testcase's classname.
   Otherwise, "unknown" will be return as component name.
   """
   sComponent = "unknown"

   if dConfig != None and "components" in dConfig:
      # component info as object in json file
      if isinstance(dConfig["components"], dict):
         for cmpt in dConfig["components"]:
            # component name maps with an array of classnames
            if isinstance(dConfig["components"][cmpt], list):
               bFound = False
               for clsName in dConfig["components"][cmpt]:
                  if clsName in sTestClassname:
                     sComponent = cmpt
                     bFound = True
                     break
               if bFound:
                  break
            # component maps with single classname
            elif isinstance(dConfig["components"][cmpt], str):
               if dConfig["components"][cmpt] in sTestClassname:
                  sComponent = cmpt
                  break
      # component info as string in json file
      elif isinstance(dConfig["components"], str) and dConfig["components"].strip() != "":
         sComponent = dConfig["components"]

   return sComponent

def process_config_file(config_file):
   """
Parse information from configuration file:

*  ``component``:
   
   .. code:: python

      {
         "components" : {
            "componentA" : "componentA/path/to/testcase",
            "componentB" : "componentB/path/to/testcase",
            "componentC" : [
               "componentC1/path/to/testcase",
               "componentC2/path/to/testcase"
            ]
         }
      }

   Then all testcases which their paths contain ``componentA/path/to/testcase`` 
   will be belong to ``componentA``, ...

**Arguments:**

*  ``config_file``

   / *Condition*: required / *Type*: str /

   Path to configuration file.

**Returns:**

*  ``dConfig``

   / *Type*: dict /
   
   Configuration object.
   """

   with open(config_file) as f:
      try:
         dConfig = json.load(f)
      except Exception as reason:
         Logger.log_error(f"Cannot parse the json file '{config_file}'. Reason: {reason}", fatal_error=True)

   if not is_valid_config(dConfig, bExitOnFail=False):
      Logger.log_error("Error in configuration file '%s'."%config_file, fatal_error=True)

   return dConfig

def process_test(db, test, file_id, test_result_id, component_name, test_number, start_time):
   """
Process test case data and create new test case record.

**Arguments:**

*  ``db``

   / *Condition*: required / *Type*: `CDataBase` object /

   CDataBase object.

*  ``test``

   / *Condition*: required / *Type*: `etree._Element` object /

   Robot test object.

*  ``file_id``

   / *Condition*: required / *Type*: int /

   File ID for mapping.

*  ``test_result_id``

   / *Condition*: required / *Type*: str /

   Test result ID for mapping.

*  ``component_name``

   / *Condition*: required / *Type*: str /

   Component name which this test case is belong to.

*  ``test_number``

   / *Condition*: required / *Type*: int /

   Order of test case in file.

*  ``start_time``

   / *Condition*: required / *Type*: `datetime` object /

   Start time of testcase.

**Returns:**

   / *Type*: float /

   Duration (in second) of test execution.
   """
   _tbl_case_name  = truncate_db_str_field(test.get("name"), DB_STR_FIELD_MAXLENGTH["name"])
   _tbl_case_issue = ""
   _tbl_case_tcid  = ""
   _tbl_case_fid   = ""
   _tbl_case_testnumber  = test_number
   _tbl_case_repeatcount = 1
   _tbl_case_component   = truncate_db_str_field(component_name, DB_STR_FIELD_MAXLENGTH["component"])
   _tbl_case_time_start  = datetime.strftime(start_time, DB_DATETIME_FORMAT)

   try:
      _tbl_case_result_main, _tbl_case_lastlog, _tbl_case_result_return = get_test_result(test)
   except Exception as reason:
      Logger.log_error(f"Error when getting PyTest result of test '{_tbl_case_name}'. Reason: {reason}", fatal_error=True)
      return

   _tbl_case_result_state   = "complete" 
   _tbl_case_counter_resets = 0
   _tbl_test_result_id = test_result_id
   _tbl_file_id = file_id
   
   if not Logger.dryrun:
      tbl_case_id = db.nCreateNewSingleTestCase(_tbl_case_name,
                                                _tbl_case_issue,
                                                _tbl_case_tcid,
                                                _tbl_case_fid,
                                                _tbl_case_testnumber,
                                                _tbl_case_repeatcount,
                                                _tbl_case_component,
                                                _tbl_case_time_start,
                                                _tbl_case_result_main,
                                                _tbl_case_result_state,
                                                _tbl_case_result_return,
                                                _tbl_case_counter_resets,
                                                _tbl_case_lastlog,
                                                _tbl_test_result_id,
                                                _tbl_file_id
                                             )
   else:
      tbl_case_id = "testcase id for dryrun"
   Logger.log("Created test case result for test '%s' successfully: %s"%(_tbl_case_name,str(tbl_case_id)), indent=4)

   return float(test.get("time"))

def process_suite(db, suite, _tbl_test_result_id, dConfig=None):
   """
Process to the lowest suite level (test file):

* Create new file and its header information
* Then, process all child test cases

**Arguments:**

*  ``db``

   / *Condition*: required / *Type*: `CDataBase` object /

   CDataBase object.

*  ``suite``

   / *Condition*: required / *Type*: `etree._Element` object /

   Robot suite object.

*  ``_tbl_test_result_id``

   / *Condition*: required / *Type*: str /

   UUID of test result for importing.

*  ``dConfig``

   / *Condition*: required / *Type*: dict / *Default*: None /

   Configuration data which is parsed from given json configuration file.

**Returns:**

(*no returns*)  
   """

   # File metadata
   previous_file_name = ""
   _tbl_file_id = None
   _tbl_file_tester_account = dConfig["tester"]
   _tbl_file_tester_machine = suite.get("hostname")
   _tbl_file_time_start = suite.get("timestamp")
   test_start_time      = datetime.strptime(_tbl_file_time_start, PYTEST_DATETIME_FORMAT)
   _tbl_file_time_end   = datetime.strftime(test_start_time + timedelta(seconds=float(suite.get("time"))), DB_DATETIME_FORMAT)

   test_number = 1
   for test in suite.iterchildren("testcase"):
      _tbl_file_name = test.get("classname")
      component_name = process_component_info(dConfig, _tbl_file_name)
      # Create new testfile if not existing in this execution (different classname with previous one)
      if previous_file_name != _tbl_file_name:
         _tbl_header_testtoolconfiguration_testtoolname      = ""
         _tbl_header_testtoolconfiguration_testtoolversion   = ""
         _tbl_header_testtoolconfiguration_pythonversion     = ""
         if dConfig["testtool"]:
            sFindstring = "([a-zA-Z\s\_]+[^\s])\s+([\d\.rcab]+)\s+\(Python\s+(.*)\)"
            oTesttool = re.search(sFindstring, dConfig["testtool"])
            if oTesttool:
               _tbl_header_testtoolconfiguration_testtoolname    = truncate_db_str_field(oTesttool.group(1), DB_STR_FIELD_MAXLENGTH["testtoolconfiguration_testtoolname"])
               _tbl_header_testtoolconfiguration_testtoolversion = truncate_db_str_field(oTesttool.group(2), DB_STR_FIELD_MAXLENGTH["testtoolconfiguration_testtoolversionstring"])
               _tbl_header_testtoolconfiguration_pythonversion   = truncate_db_str_field(oTesttool.group(3), DB_STR_FIELD_MAXLENGTH["testtoolconfiguration_pythonversion"])

         _tbl_header_testtoolconfiguration_projectname     = dConfig["variant"]
         _tbl_header_testtoolconfiguration_logfileencoding = "UTF-8"
         _tbl_header_testtoolconfiguration_testfile        = truncate_db_str_field(_tbl_file_name, DB_STR_FIELD_MAXLENGTH["name"])
         _tbl_header_testtoolconfiguration_logfilepath     = ""
         _tbl_header_testtoolconfiguration_logfilemode     = ""
         _tbl_header_testtoolconfiguration_ctrlfilepath    = ""
         _tbl_header_testtoolconfiguration_configfile      = ""
         _tbl_header_testtoolconfiguration_confname        = ""

         _tbl_header_testfileheader_author           = truncate_db_str_field(dConfig["tester"], DB_STR_FIELD_MAXLENGTH["tester_account"])
         _tbl_header_testfileheader_project          = dConfig["variant"]
         _tbl_header_testfileheader_testfiledate     = ""
         _tbl_header_testfileheader_version_major    = ""
         _tbl_header_testfileheader_version_minor    = ""
         _tbl_header_testfileheader_version_patch    = ""
         _tbl_header_testfileheader_keyword          = ""
         _tbl_header_testfileheader_shortdescription = ""
         _tbl_header_testexecution_useraccount       = truncate_db_str_field(dConfig["tester"], DB_STR_FIELD_MAXLENGTH["tester_account"])
         _tbl_header_testexecution_computername      = truncate_db_str_field(_tbl_file_tester_machine, DB_STR_FIELD_MAXLENGTH["tester_machine"])

         _tbl_header_testrequirements_documentmanagement = ""
         _tbl_header_testrequirements_testenvironment    = ""
         
         _tbl_header_testbenchconfig_name    = ""
         _tbl_header_testbenchconfig_data    = ""
         _tbl_header_preprocessor_filter     = ""
         _tbl_header_preprocessor_parameters = ""

         if not Logger.dryrun:
            _tbl_file_id = db.nCreateNewFile(_tbl_file_name,
                                             _tbl_file_tester_account,
                                             _tbl_file_tester_machine,
                                             _tbl_file_time_start,
                                             _tbl_file_time_end,
                                             _tbl_test_result_id)
            db.vCreateNewHeader(_tbl_file_id,
                              _tbl_header_testtoolconfiguration_testtoolname,
                              _tbl_header_testtoolconfiguration_testtoolversion,
                              _tbl_header_testtoolconfiguration_projectname,
                              _tbl_header_testtoolconfiguration_logfileencoding,
                              _tbl_header_testtoolconfiguration_pythonversion,
                              _tbl_header_testtoolconfiguration_testfile,
                              _tbl_header_testtoolconfiguration_logfilepath,
                              _tbl_header_testtoolconfiguration_logfilemode,
                              _tbl_header_testtoolconfiguration_ctrlfilepath,
                              _tbl_header_testtoolconfiguration_configfile,
                              _tbl_header_testtoolconfiguration_confname,

                              _tbl_header_testfileheader_author,
                              _tbl_header_testfileheader_project,
                              _tbl_header_testfileheader_testfiledate,
                              _tbl_header_testfileheader_version_major,
                              _tbl_header_testfileheader_version_minor,
                              _tbl_header_testfileheader_version_patch,
                              _tbl_header_testfileheader_keyword,
                              _tbl_header_testfileheader_shortdescription,
                              _tbl_header_testexecution_useraccount,
                              _tbl_header_testexecution_computername,

                              _tbl_header_testrequirements_documentmanagement,
                              _tbl_header_testrequirements_testenvironment,

                              _tbl_header_testbenchconfig_name,
                              _tbl_header_testbenchconfig_data,
                              _tbl_header_preprocessor_filter,
                              _tbl_header_preprocessor_parameters 
                              )
         else:
            _tbl_file_id = "file id for dryrun"
         Logger.log("Created test file result for classname '%s' successfully: %s"%(_tbl_file_name, str(_tbl_file_id)), indent=2)
         previous_file_name = _tbl_file_name
   
      # Process testcase
      if _tbl_file_id:
         duration = process_test(db, test, _tbl_file_id, _tbl_test_result_id, component_name, test_number, test_start_time)
         test_start_time += timedelta(seconds=duration)
         test_number += 1
      else:
         Logger.log_error(f"No found testfile ID for classname {_tbl_file_name}.", fatal_error=True)

def PyTestLog2DB(args=None):
   """
Import pytest results from ``*.xml`` file(s) to TestResultWebApp's database.

Flow to import PyTest results to database: 

1. Process provided arguments from command line.
2. Parse PyTest results.
3. Connect to database.
4. Import results into database.
5. Disconnect from database.

**Arguments:**

*  ``args``

   / *Condition*: required / *Type*: `ArgumentParser` object /

   Argument parser object which contains:

   * `resultxmlfile` : path to the xml result file or directory of result files to be imported.
   * `server` : server which hosts the database (IP or URL).
   * `user` : user for database login.
   * `password` : password for database login.
   * `database` : database name.
   * `recursive` : if True, then the path is searched recursively for log files to be imported.
   * `dryrun` : if True, then just check the RQM authentication and show what would be done.
   * `append` : if True, then allow to append new result(s) to existing execution result UUID which is provided by -UUID argument.
   * `UUID` : UUID used to identify the import and version ID on TestResultWebApp.
   * `config` : configuration json file for component mapping information.

**Returns:**

(*no returns*)
   """
   # 1. process provided arguments from command line as default
   args = __process_commandline()
   Logger.config(dryrun=args.dryrun)

   # Validate provide result *xml file/folder
   sLogFileType="NONE"
   if os.path.exists(args.resultxmlfile):
      sLogFileType="PATH"
      if os.path.isfile(args.resultxmlfile):
         sLogFileType="FILE"  
   else:
      Logger.log_error("Resultxmlfile is not existing: '%s'" % str(args.resultxmlfile), fatal_error=True)

   listEntries=[]
   if sLogFileType=="FILE":
      listEntries.append(args.resultxmlfile)
   else:
      if args.recursive:
         Logger.log("Searching result *.xml files recursively...")
         for root, dirs, files in os.walk(args.resultxmlfile):
            for file in files:
               if file.endswith(".xml"):
                  listEntries.append(os.path.join(root, file))
                  Logger.log(os.path.join(root, file), indent=2)
      else:
         Logger.log("Searching result *.xml files...")
         for file in os.listdir(args.resultxmlfile):
            if file.endswith(".xml"):
               listEntries.append(os.path.join(args.resultxmlfile, file))
               Logger.log(os.path.join(args.resultxmlfile, file), indent=2)

      # Terminate tool with error when no logfile under provided resultxmlfile folder
      if len(listEntries) == 0:
         Logger.log_error("No resultxmlfile under '%s' folder." % str(args.resultxmlfile), fatal_error=True)

   # Validate provided UUID
   if args.UUID!=None:
      if is_valid_uuid(args.UUID):
         pass
      else:
         Logger.log_error("the uuid provided is not valid: '%s'" % str(args.UUID), fatal_error=True)

   # Validate provided configuration file (component, variant, version_sw)
   dConfig = {}
   if args.config != None:
      if os.path.isfile(args.config):
         dConfig = process_config_file(args.config)
      else:
         Logger.log_error("The provided config file is not existing: '%s'" % str(args.config), fatal_error=True)

   # Set default value for missing metadata bases on DEFAULT_METADATA
   for key in DEFAULT_METADATA:
      if key not in dConfig:
         dConfig[key] = DEFAULT_METADATA[key]

   # 2. Parse results from PyTest xml result file(s)
   pytest_result = parse_pytest_xml(*listEntries)

   # 3. Connect to database
   db=CDataBase()
   try:
      db.connect(args.server,
                 args.user,
                 args.password,
                 args.database)
   except Exception as reason:
      Logger.log_error("Could not connect to database: '%s'" % str(reason), fatal_error=True)

   # 4. Import results into database
   #    Create new execution result in database
   #    |
   #    '---Create new file result(s)
   #        |
   #        '---Create new test result(s) 
   try:
      # Process project/variant
      # Project/Variant name is limited to 20 chars, otherwise an error is raised
      _tbl_prj_project = _tbl_prj_variant = validate_db_str_field("variant", dConfig["variant"])

      # Process versions info
      # Versions info is limited to 100 chars, otherwise an error is raised
      _tbl_result_version_sw_target = validate_db_str_field("version_sw_target", dConfig["version_sw"])
      _tbl_result_version_hardware  = truncate_db_str_field(dConfig["version_hw"], DB_STR_FIELD_MAXLENGTH["version_hardware"])
      _tbl_result_version_sw_test   = truncate_db_str_field(dConfig["version_test"], DB_STR_FIELD_MAXLENGTH["version_sw_test"])

      # Set version as start time of the execution if not provided in metadata
      # Format: %Y%m%d_%H%M%S from %Y-%m-%d %H:%M:%S
      if _tbl_result_version_sw_target=="":
         _tbl_result_version_sw_target = datetime.strftime(datetime.strptime(pytest_result.get("starttime"), DB_DATETIME_FORMAT), "%Y%m%d_%H%M%S")

      # Process branch info from software version
      _tbl_prj_branch = get_branch_from_swversion(_tbl_result_version_sw_target)

      # Process UUID info
      if args.UUID != None:
         _tbl_test_result_id = args.UUID
      else:
         _tbl_test_result_id = str(uuid.uuid4())
         if args.append:
            Logger.log_warning("'--append' argument should be used in combination with '--UUID <UUID>` argument.")
      
      # Process start/end time info
      _tbl_result_time_start = pytest_result.get("starttime")
      _tbl_result_time_end   = pytest_result.get("endtime")

      # Process other info
      _tbl_result_interpretation = ""
      _tbl_result_jenkinsurl     = ""
      _tbl_result_reporting_qualitygate = ""

      # Process new test result
      if not Logger.dryrun:
         db.sCreateNewTestResult(_tbl_prj_project,
                                 _tbl_prj_variant,
                                 _tbl_prj_branch,
                                 _tbl_test_result_id,
                                 _tbl_result_interpretation,
                                 _tbl_result_time_start,
                                 _tbl_result_time_end,
                                 _tbl_result_version_sw_target,
                                 _tbl_result_version_sw_test,
                                 _tbl_result_version_hardware,
                                 _tbl_result_jenkinsurl,
                                 _tbl_result_reporting_qualitygate)
      Logger.log("Created test execution result for version '%s' successfully: %s"%(_tbl_result_version_sw_target,str(_tbl_test_result_id)))
   except Exception as reason:
      # MySQL error code:
      # Error Code   | SQLSTATE	|Error	      |Description                     
      # -------------+-----------+--------------+-------------------------------
      # 1062	      | 23000	   |ER_DUP_ENTRY	|Duplicate entry '%s' for key %d
      if reason.args[0] == 1062:
         # check -append argument
         if args.append:
            Logger.log(f"Append to existing test execution result UUID '{_tbl_test_result_id}'.")
         else:
            error_indent = len(Logger.prefix_fatalerror)*' '
            Logger.log_error(f"Execution result with UUID '{_tbl_test_result_id}' is already existing. \
               \n{error_indent}Please use other UUID (or remove '--UUID' argument from your command) for new execution result. \
               \n{error_indent}Or add '--append' argument in your command to append new result(s) to this existing UUID.", 
               fatal_error=True)
      else:
         Logger.log_error("Could not create new execution result. Reason: %s"%reason, fatal_error=True)

   for suite in pytest_result.iterchildren("testsuite"):
      process_suite(db, suite, _tbl_test_result_id, dConfig)

   if not Logger.dryrun:
      db.vUpdateEvtbls()
      db.vFinishTestResult(_tbl_test_result_id)
      if args.append:
         db.vUpdateEvtbl(_tbl_test_result_id)

   # 5. Disconnect from database
   db.disconnect()
   Logger.log("All test results are written to database successfully.")

if __name__=="__main__":
   PyTestLog2DB()
