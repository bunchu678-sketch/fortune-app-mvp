"""PDF source reuse, API isolation and bounded converter lifecycle tests."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from report_export_cases import FORM,api_call,unpack,sheet_cells
from fortune_service import calculate_fortune
from history_repository import SQLiteHistoryRepository,HistoryError
from history_service import HistoryService
from report_export_service import ExportTokens,export_reading
from report_pdf import export_pdf_reading
import pdf_converter as pc
from report_data import ReportError

PDF=b'%PDF-1.7\nunit-test converter output\n%%EOF\n'


class RecordingConverter:
    def __init__(self):self.inputs=[]
    def convert(self,xlsx):self.inputs.append(xlsx);return PDF


class PdfCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=calculate_fortune(FORM)
        assert cls.result['ok']

    def source(self,result=None,form=None):
        tokens=ExportTokens();token=tokens.issue('one',form or FORM,result or self.result)
        return tokens,{'export_token':token}

    def test_pdf_receives_exact_completed_excel_and_same_filename(self):
        tokens,payload=self.source();adapter=RecordingConverter()
        xname,xlsx=export_reading('one',payload,tokens=tokens)
        name,body=export_pdf_reading('one',payload,tokens=tokens,converter=adapter)
        self.assertEqual(name,xname[:-5]+'.pdf');self.assertEqual(body,PDF)
        # ZIP creation timestamps can differ; all completed workbook entries must match.
        self.assertEqual(len(adapter.inputs),1)
        self.assertEqual(unpack(adapter.inputs[0]),unpack(xlsx))

    def test_nameless_and_safe_names_reuse_excel_rule(self):
        for surname,given in [('', ''),('危険/名:*?','太郎<>')]:
            tokens,payload=self.source(form={**FORM,'surname':surname,'givenName':given})
            xname,_=export_reading('one',payload,tokens=tokens)
            pname,_=export_pdf_reading('one',payload,tokens=tokens,converter=RecordingConverter())
            self.assertEqual(pname,xname[:-5]+'.pdf')
            self.assertFalse(any(c in pname for c in '/\\:*?"<>|'))
            if not surname:self.assertIn('無記名',pname)

    def test_invalid_payload_and_foreign_token_never_convert(self):
        tokens,payload=self.source();adapter=RecordingConverter()
        for owner,body in [('two',payload),('one',{**payload,'format':'pdf'}),('one',{'reading_id':'x','user_id':'one'})]:
            with self.assertRaises(ReportError):export_pdf_reading(owner,body,tokens=tokens,converter=adapter)
        self.assertEqual(adapter.inputs,[])

    def test_private_fields_removed_before_converter(self):
        result=deepcopy(self.result)
        result.update({key:'PDF_PRIVATE_SENTINEL_'+key for key in ('memo','past_memos','user_id','person_id','group_id','reading_id','app_version','calculation_logic_version')})
        for stage in result['personality']['life_stage_tsuhensei']:stage['outer_private_comment']='PDF_PRIVATE_SENTINEL_COMMENT'
        tokens,payload=self.source(result);adapter=RecordingConverter()
        export_pdf_reading('one',payload,tokens=tokens,converter=adapter)
        self.assertNotIn(b'PDF_PRIVATE_SENTINEL',b''.join(unpack(adapter.inputs[0]).values()))

    def test_saved_snapshot_owner_deleted_and_no_recalculation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=SQLiteHistoryRepository(Path(directory)/'history.sqlite3')
            result=deepcopy(self.result);result['yearly_overall']['comment']='保存当時の公開コメント'
            row=HistoryService(repo).create('one',{'input_snapshot':{'form':FORM},'result_snapshot':result,'memo':'PDF_PRIVATE_MEMO'})
            adapter=RecordingConverter()
            with patch('fortune_service.calculate_fortune',side_effect=AssertionError('must not recalculate')):
                export_pdf_reading('one',{'reading_id':row['id']},repo,converter=adapter)
            parts=unpack(adapter.inputs[0]);raw=b''.join(parts.values())
            self.assertIn('保存当時の公開コメント'.encode(),raw);self.assertNotIn(b'PDF_PRIVATE_MEMO',raw)
            self.assertEqual(sheet_cells(parts)['M3'],'38')
            for value in (row['id'],row['person_id'],row['group_id']):self.assertNotIn(value.encode(),raw)
            with self.assertRaises(HistoryError):export_pdf_reading('two',{'reading_id':row['id']},repo,converter=adapter)
            repo.soft_delete('one',row['id'])
            with self.assertRaises(HistoryError):export_pdf_reading('one',{'reading_id':row['id']},repo,converter=adapter)
            self.assertEqual(len(adapter.inputs),1)

    def test_excel_failure_does_not_invoke_converter(self):
        tokens,payload=self.source();adapter=RecordingConverter()
        with patch('report_export_service.render_xlsx',side_effect=ReportError('テンプレート不一致',503)):
            with self.assertRaises(ReportError):export_pdf_reading('one',payload,tokens=tokens,converter=adapter)
        self.assertEqual(adapter.inputs,[])

    def test_api_new_pdf_headers_and_excel_still_works(self):
        adapter=RecordingConverter()
        with patch.dict(os.environ,{'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one'}),patch('report_pdf.get_pdf_converter',return_value=adapter):
            status,_,body=asyncio.run(api_call('POST','/api/fortune',FORM));self.assertEqual(status,200)
            token=json.loads(body)['excel_export_token']
            status,headers,body=asyncio.run(api_call('POST','/api/export/pdf',{'export_token':token}))
            self.assertEqual(status,200);self.assertEqual(body,PDF)
            self.assertEqual(headers[b'content-type'],b'application/pdf')
            self.assertEqual(headers[b'cache-control'],b'no-store');self.assertEqual(headers[b'x-content-type-options'],b'nosniff')
            self.assertIn(quote('鑑定書_出力試験太郎_2026-10-05.pdf',safe='').encode(),headers[b'content-disposition'])
            status,_,body=asyncio.run(api_call('POST','/api/export/excel',{'export_token':token}))
            self.assertEqual(status,200);self.assertEqual(unpack(body),unpack(adapter.inputs[0]))
        with patch.dict(os.environ,{'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'two'}),patch('report_pdf.get_pdf_converter',return_value=adapter):
            self.assertEqual(asyncio.run(api_call('POST','/api/export/pdf',{'export_token':token}))[0],404)
        self.assertEqual(len(adapter.inputs),1)

    def test_api_saved_foreign_owner_and_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.sqlite3';repo=SQLiteHistoryRepository(path)
            row=HistoryService(repo).create('one',{'input_snapshot':{'form':FORM},'result_snapshot':self.result,'memo':'PDF_PRIVATE_MEMO'})
            env={'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one','FORTUNE_HISTORY_DB_PATH':str(path)}
            adapter=RecordingConverter()
            with patch.dict(os.environ,env),patch('report_pdf.get_pdf_converter',return_value=adapter):
                self.assertEqual(asyncio.run(api_call('POST','/api/export/pdf',{'reading_id':row['id']}))[0],200)
            with patch.dict(os.environ,{**env,'FORTUNE_HISTORY_DEV_USER_ID':'two'}),patch('report_pdf.get_pdf_converter',return_value=adapter):
                self.assertEqual(asyncio.run(api_call('POST','/api/export/pdf',{'reading_id':row['id']}))[0],404)
            repo.soft_delete('one',row['id'])
            with patch.dict(os.environ,env),patch('report_pdf.get_pdf_converter',return_value=adapter):
                self.assertEqual(asyncio.run(api_call('POST','/api/export/pdf',{'reading_id':row['id']}))[0],404)
            self.assertEqual(len(adapter.inputs),1)

    def test_api_converter_unavailable_does_not_break_excel(self):
        with patch.dict(os.environ,{'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one'}),patch('report_pdf.get_pdf_converter',return_value=pc.UnavailablePdfConverter()):
            _,_,body=asyncio.run(api_call('POST','/api/fortune',FORM));payload={'export_token':json.loads(body)['excel_export_token']}
            status,_,body=asyncio.run(api_call('POST','/api/export/pdf',payload))
            self.assertEqual(status,503);self.assertEqual(json.loads(body)['code'],'converter_unavailable')
            self.assertEqual(asyncio.run(api_call('POST','/api/export/excel',payload))[0],200)

    def test_api_timeout_failure_and_excel_generation_error(self):
        with patch.dict(os.environ,{'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one'}):
            _,_,body=asyncio.run(api_call('POST','/api/fortune',FORM));payload={'export_token':json.loads(body)['excel_export_token']}
            for code,status in [('conversion_timeout',504),('com_start_failed',503),('pdf_generation_failed',500),('output_missing',500)]:
                adapter=RecordingConverter();adapter.convert=lambda _:(_ for _ in ()).throw(pc.PdfConversionError(code,'変換に失敗しました。',status))
                with patch('report_pdf.get_pdf_converter',return_value=adapter):
                    actual,_,body=asyncio.run(api_call('POST','/api/export/pdf',payload))
                    self.assertEqual(actual,status);self.assertEqual(json.loads(body)['code'],code)
                    self.assertNotIn(b'Traceback',body);self.assertNotIn(str(ROOT).encode(),body)
            with patch('report_export_service.render_xlsx',side_effect=ReportError('テンプレート不一致',503)):
                status,_,body=asyncio.run(api_call('POST','/api/export/pdf',payload))
                self.assertEqual(status,503);self.assertEqual(json.loads(body)['code'],'excel_generation_failed')

    def test_api_invalid_payload_and_no_auth(self):
        with patch.dict(os.environ,{'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one'}):
            for payload in ({'result_snapshot':self.result},{'export_token':'x','converter':'windows_excel'},[]):
                self.assertEqual(asyncio.run(api_call('POST','/api/export/pdf',payload))[0],422)
        with patch.dict(os.environ,{'FORTUNE_ENV':'production','FORTUNE_HISTORY_DEV_USER_ID':'one'}):
            self.assertEqual(asyncio.run(api_call('POST','/api/export/pdf',{'export_token':'x'}))[0],401)


class ConverterCases(unittest.TestCase):
    def native(self,behavior='ok',code='pdf_generation_failed'):
        directories=[];calls=[]
        def run(command,**kwargs):
            calls.append((command,kwargs))
            if 'stop_owned_excel.ps1' in command[4]:
                if behavior=='cleanup_error':raise subprocess.CalledProcessError(1,command)
                return subprocess.CompletedProcess(command,0,b'',b'')
            source=Path(command[command.index('-InputPath')+1]);target=Path(command[command.index('-OutputPath')+1])
            directories.append(source.parent);self.assertEqual(source.read_bytes(),b'completed-xlsx')
            if behavior in ('ok','timeout','cleanup_error'):target.write_bytes(PDF)
            if behavior=='invalid':target.write_bytes(b'not a PDF')
            if behavior=='timeout':raise subprocess.TimeoutExpired(command,kwargs['timeout'])
            if behavior=='launch_error':raise OSError('private/internal path')
            result={'ok':behavior!='failure','code':code if behavior=='failure' else 'ok'}
            return subprocess.CompletedProcess(command,1 if behavior=='failure' else 0,('PDF_RESULT='+json.dumps(result)).encode(),b'')
        original=Path.is_file
        def available(path):return path.name in ('powershell.exe','windows_excel_pdf.ps1','stop_owned_excel.ps1') or original(path)
        with patch('pdf_converter.sys.platform','win32'),patch('pdf_converter.Path.is_file',available),patch('pdf_converter.subprocess.CREATE_NO_WINDOW',0,create=True),patch('pdf_converter.subprocess.run',side_effect=run):
            try:
                result=pc.WindowsExcelPdfConverter(timeout=2).convert(b'completed-xlsx')
                return result, None, calls, directories
            except pc.PdfConversionError as exc:return None,exc,calls,directories

    def check_cleaned(self,directories):
        self.assertTrue(directories)
        self.assertTrue(all(not path.exists() for path in directories))

    def test_success_cleanup_and_bounded_worker(self):
        result,error,calls,dirs=self.native();self.assertEqual(result,PDF);self.assertIsNone(error)
        self.assertEqual(len(calls),2);self.assertEqual(calls[0][1]['timeout'],2);self.check_cleaned(dirs)

    def test_timeout_cleanup_partial_output(self):
        _,error,calls,dirs=self.native('timeout');self.assertEqual(error.code,'conversion_timeout');self.assertEqual(error.status,504)
        self.assertEqual(len(calls),2);self.check_cleaned(dirs)

    def test_com_launch_open_and_export_failures_cleanup(self):
        for code in ('converter_unavailable','excel_launch_failed','com_start_failed','excel_open_failed','pdf_generation_failed','output_missing'):
            with self.subTest(code=code):
                _,error,calls,dirs=self.native('failure',code);self.assertEqual(error.code,code)
                self.assertEqual(len(calls),2);self.check_cleaned(dirs)

    def test_missing_output_cleanup(self):
        _,error,_,dirs=self.native('missing');self.assertEqual(error.code,'output_missing');self.check_cleaned(dirs)

    def test_invalid_output_cleanup(self):
        _,error,_,dirs=self.native('invalid');self.assertEqual(error.code,'output_invalid');self.check_cleaned(dirs)

    def test_worker_cannot_start_cleanup(self):
        _,error,_,dirs=self.native('launch_error');self.assertEqual(error.code,'converter_unavailable');self.check_cleaned(dirs)

    def test_cleanup_failure_is_controlled(self):
        _,error,_,dirs=self.native('cleanup_error');self.assertEqual(error.code,'cleanup_failed');self.check_cleaned(dirs)

    def test_non_windows_import_and_conversion_unavailable(self):
        with patch('pdf_converter.sys.platform','linux'),patch('pdf_converter.subprocess.run',side_effect=AssertionError('must not run Windows tools')):
            with self.assertRaises(pc.PdfConversionError) as caught:pc.WindowsExcelPdfConverter().convert(b'x')
            self.assertEqual(caught.exception.status,503)
            with patch.dict(os.environ,{},clear=True):self.assertIsInstance(pc.get_pdf_converter(),pc.UnavailablePdfConverter)

    def test_engine_selection_only_at_call_time(self):
        with patch.dict(os.environ,{'FORTUNE_ENV':'development','FORTUNE_PDF_CONVERTER':'windows_excel'}):
            self.assertIsInstance(pc.get_pdf_converter(),pc.WindowsExcelPdfConverter)
        with patch.dict(os.environ,{'FORTUNE_PDF_CONVERTER':'disabled'}):self.assertIsInstance(pc.get_pdf_converter(),pc.UnavailablePdfConverter)

    def test_busy_converter_does_not_create_files(self):
        with patch('pdf_converter.sys.platform','win32'),patch('pdf_converter.Path.is_file',return_value=True),patch('pdf_converter._excel_gate') as gate:
            gate.acquire.return_value=False
            with self.assertRaises(pc.PdfConversionError) as caught:pc.WindowsExcelPdfConverter().convert(b'x')
            self.assertEqual(caught.exception.code,'converter_busy');gate.release.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
