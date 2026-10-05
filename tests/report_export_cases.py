"""Excel report contract, official data, snapshot and owner-isolation tests."""
from copy import deepcopy
from io import BytesIO
import asyncio
import hashlib
import json
import posixpath
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from fortune_service import calculate_fortune
from history_repository import SQLiteHistoryRepository, HistoryError
from history_service import HistoryService
from report_data import build_reading_report, difference, ReportError
from report_xlsx import render_xlsx, TEMPLATE_PATH, TEMPLATE_SHA256
from report_export_service import ExportTokens, export_reading
from tier_b import api_app

FORM={"surname":"出力試験","givenName":"太郎","name":"出力試験太郎","birthDate":"1988-08-12",
      "birthTime":"09:00","birthTimeUnknown":False,"gender":"男性","birthPlace":"東京都",
      "readingDate":"2026-10-05","includeGogyoVariants":True,"productAutoBoundary":True}
NS={"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main","a":"http://schemas.openxmlformats.org/drawingml/2006/main",
    "x":"http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing","c":"http://schemas.openxmlformats.org/drawingml/2006/chart"}

def unpack(body):
    with ZipFile(BytesIO(body)) as z:
        assert z.testzip() is None
        return {n:z.read(n) for n in z.namelist()}

def sheet_cells(parts):
    root=ET.fromstring(parts['xl/worksheets/sheet2.xml'])
    return {c.get('r'):c.findtext('s:v','',NS) if c.get('t')!='inlineStr' else c.findtext('s:is/s:t','',NS)
            for c in root.findall('s:sheetData/s:row/s:c',NS)}

async def api_call(method,path,payload):
    output=[];sent=False;raw=json.dumps(payload).encode()
    async def receive():
        nonlocal sent
        if sent:return {"type":"http.disconnect"}
        sent=True;return {"type":"http.request","body":raw,"more_body":False}
    async def send(item):output.append(item)
    scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.3"},"http_version":"1.1","method":method,
           "scheme":"http","path":path,"raw_path":path.encode(),"query_string":b"","root_path":"",
           "headers":[(b"content-type",b"application/json")],"server":("test",80),"client":("test",1)}
    await api_app()(scope,receive,send)
    start=next(x for x in output if x['type']=='http.response.start')
    body=b''.join(x.get('body',b'') for x in output if x['type']=='http.response.body')
    return start['status'],dict(start['headers']),body


class ReportCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=calculate_fortune(FORM)
        assert cls.result['ok']
        cls.report=build_reading_report(FORM,cls.result)
        cls.parts=unpack(render_xlsx(cls.report))
        cls.cells=sheet_cells(cls.parts)

    def test_approved_template_unchanged(self):
        self.assertEqual(hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest(),TEMPLATE_SHA256)

    def test_valid_xml_and_zip(self):
        for path,data in self.parts.items():
            if path.endswith(('.xml','.rels')): ET.fromstring(data)

    def test_package_relationships_have_targets(self):
        for name,data in self.parts.items():
            if not name.endswith('.rels'):continue
            source_dir=name.split('/_rels/')[0] if '/_rels/' in name else ''
            for rel in ET.fromstring(data):
                if rel.get('TargetMode')=='External':continue
                target=rel.get('Target')
                resolved=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(source_dir,target))
                self.assertIn(resolved,self.parts,(name,target))

    def test_print_settings_and_break(self):
        sheet=ET.fromstring(self.parts['xl/worksheets/sheet2.xml'])
        self.assertEqual(sheet.find('s:pageSetup',NS).get('scale'),'85')
        self.assertEqual(sheet.find('s:pageSetup',NS).get('paperSize'),'9')
        self.assertEqual(sheet.find('s:rowBreaks/s:brk',NS).get('id'),'35')
        workbook=ET.fromstring(self.parts['xl/workbook.xml'])
        areas=[n.text for n in workbook.findall('s:definedNames/s:definedName',NS) if n.get('name')=='_xlnm.Print_Area']
        self.assertTrue(any('$A$1:$O$68' in x for x in areas))

    def test_drawing_anchors_and_objects_preserved(self):
        with ZipFile(TEMPLATE_PATH) as z:old=ET.fromstring(z.read('xl/drawings/drawing2.xml'))
        new=ET.fromstring(self.parts['xl/drawings/drawing2.xml'])
        self.assertEqual(len(old),len(new))
        for a,b in zip(old,new):
            for local in ('from','to','pos','ext'):
                x,y=a.find('x:'+local,NS),b.find('x:'+local,NS)
                self.assertEqual(ET.tostring(x) if x is not None else None,ET.tostring(y) if y is not None else None)
        self.assertEqual(len(new.findall('.//c:chart',NS)),5)
        self.assertEqual(len(new.findall('.//x:sp',NS)),len(old.findall('.//x:sp',NS)))

    def test_basic_information(self):
        for key,expected in {'D3':'出力試験太郎','G3':'1988/08/12','J3':'09:00','L3':'東京都','M3':'38','N3':'男性'}.items():self.assertEqual(self.cells[key],expected)

    def test_meishiki_and_kubou(self):
        for col,key in zip('DEFG',('hour','day','month','year')):
            for row,field in ((7,'tenkan'),(8,'chishi'),(9,'zokkan')):self.assertEqual(self.cells[col+str(row)],self.result['meishiki'][key][field])
        self.assertEqual(self.cells['E13'],self.result['kubou'])

    def test_gogyo_A_order_and_scores(self):
        a=self.result['gogyo_variants']['A']['gogyo']
        for addr,element in zip(('K6','M8','L12','J12','I8'),a['chart_order']):self.assertEqual(self.cells[addr],f"{element} {a['scores'][element]:g}")

    def test_difference_is_A_B_and_B_C(self):
        variants={k:{'status':'available','gogyo':{'scores':{x:0 for x in '木火土金水'}}} for k in 'ABC'}
        variants['A']['gogyo']['scores']['木']=8
        variants['B']['gogyo']['scores']['木']=9
        variants['C']['gogyo']['scores']['木']=7
        self.assertEqual(difference('今年の影響',variants['A'],variants['B']),'今年の影響：木 8 → 9（+1）')
        self.assertEqual(difference('大運の影響',variants['B'],variants['C']),'大運の影響：木 9 → 7（-2）')

    def test_no_difference_and_pending(self):
        a=self.result['gogyo_variants']['A']
        self.assertEqual(difference('今年の影響',a,a),'今年の影響：五行点数に変化なし')
        self.assertIn('節入りの確認後',difference('今年の影響',a,{'status':'boundary_pending'}))

    def test_special_only_official_rows(self):
        for i in range(6):
            row=self.result['special_meishiki']['rows'][i] if i<len(self.result['special_meishiki']['rows']) else {}
            self.assertEqual(self.cells[f'C{19+i}'],row.get('判定',''))
            self.assertEqual(self.cells[f'E{19+i}'],row.get('結果',''))

    def test_no_special_and_overflow_not_truncated(self):
        r=deepcopy(self.result);r['special_meishiki']['rows']=[]
        self.assertTrue(all(build_reading_report(FORM,r).cells[f'C{19+i}']=='' for i in range(6)))
        r['special_meishiki']['rows']=[{'判定':'テスト','結果':'テスト'}]*7
        with self.assertRaises(ReportError):build_reading_report(FORM,r)

    def test_nikkan_description_and_keywords(self):
        self.assertEqual(self.report.texts['Phase5_Nikkan'],self.result['personality']['nikkan']['description'])
        self.assertIn(self.result['personality']['nikkan']['keywords'],self.cells['B25'])

    def test_life_stage_public_only_and_current(self):
        for i,row in enumerate(self.result['personality']['life_stage_tsuhensei']):
            for key in ('outer_comment','inner_comment'):
                if row[key]:self.assertIn(row[key],self.report.texts[f'Phase5_Stage{i}'])
        self.assertEqual(self.report.texts['Phase5_CurrentStage'],self.result['personality']['current_life_stage_pair']['public_comment'])

    def test_twelve_star_comments_keywords(self):
        for i,row in enumerate(self.result['personality']['juuni_unsei']['rows']):
            self.assertEqual(self.report.texts[f'Phase5_Juuni{i}'],row['public_comment'])
            self.assertIn(row['keywords'],self.cells[('C' if i%2==0 else 'I')+('39' if i<2 else '42')])

    def test_chart_sources_and_caches(self):
        thinking=self.result['personality']['juuni_unsei']['thinking']
        self.assertEqual(float(self.cells['X103']),thinking['work_type']['現場型攻め'])
        self.assertEqual(float(self.cells['R106']),.2)
        chart=ET.fromstring(self.parts['xl/charts/chart1.xml'])
        self.assertEqual([float(x.text) for x in chart.findall('.//c:val/c:numRef/c:numCache/c:pt/c:v',NS)],[30,0,20,50])

    def test_unknown_hour_and_ratio_total(self):
        form={**FORM,'birthTimeUnknown':True};r=calculate_fortune(form);report=build_reading_report(form,r)
        self.assertEqual(report.cells['J3'],'出生時刻不明')
        self.assertTrue(all(report.cells['D'+str(row)]=='' for row in (7,8,9,10,11,12)))
        scores=r['personality']['juuni_unsei']['thinking']['brain_type']
        self.assertAlmostEqual(report.chart_cells['R103'],scores['左脳']/sum(scores.values()))

    def test_no_gender_no_daiun(self):
        form={**FORM,'gender':'未選択'};r=calculate_fortune(form);report=build_reading_report(form,r)
        self.assertEqual(report.cells['C16'],'大運の影響：大運を取得できないため算出できません。')
        self.assertFalse(report.setsuboku_boundaries)
        self.assertTrue(all(report.cells[c+'56']=='' for c in 'CDEFGHIJKL'))

    def test_dynamic_setsuboku_borders(self):
        r=deepcopy(self.result)
        for i,row in enumerate(r['daiun']['rows']):row['次の大運との間が接木運']=i in (0,6)
        report=build_reading_report(FORM,r);parts=unpack(render_xlsx(report))
        sheet=ET.fromstring(parts['xl/worksheets/sheet2.xml']);styles=ET.fromstring(parts['xl/styles.xml'])
        xfs=list(styles.find('s:cellXfs',NS));borders=list(styles.find('s:borders',NS))
        cells={c.get('r'):c for c in sheet.findall('.//s:c',NS)}
        for col,expected in [('C','thick'),('F','thin'),('I','thick')]:
            xf=xfs[int(cells[col+'58'].get('s'))];border=borders[int(xf.get('borderId'))]
            self.assertEqual(border.find('s:right',NS).get('style'),expected)

    def test_year_and_months_kubou(self):
        self.assertEqual(self.cells['L60'],'2026');self.assertEqual(self.cells['E61'],self.result['yearly_overall']['tsuhensei'])
        for col,row in zip('CDEFGHIJKLMN',self.result['yearly_flow']['rows']):
            self.assertEqual(self.cells[col+'65'],row['地支'])
        self.assertTrue(self.report.kubou_months)
        self.assertEqual(self.report.texts['3'],self.result['yearly_overall']['comment'])

    def test_changed_year_not_fixed_2026(self):
        r=calculate_fortune({**FORM,'readingDate':'2027-10-05'})
        report=build_reading_report({**FORM,'readingDate':'2027-10-05'},r)
        self.assertEqual(report.cells['L60'],2027)
        self.assertEqual(report.cells['C64'],r['yearly_flow']['rows'][0]['天干'])

    def test_anonymous_and_safe_filename_and_literal_formula(self):
        form={**FORM,'surname':'','givenName':''}
        self.assertEqual(build_reading_report(form,self.result).cells['D3'],'無記名')
        form={**FORM,'surname':'=HYPERLINK("bad")/\\:*?<>|','givenName':''}
        report=build_reading_report(form,self.result)
        self.assertNotRegex(report.filename,r'[<>:"/\\|?*]')
        parts=unpack(render_xlsx(report))
        self.assertFalse(ET.fromstring(parts['xl/worksheets/sheet2.xml']).findall('.//s:f',NS))
        self.assertIn('=HYPERLINK',sheet_cells(parts)['D3'])

    def test_private_ids_and_old_calculation_absent(self):
        r=deepcopy(self.result)
        for stage in r['personality']['life_stage_tsuhensei']:stage['outer_private_comment']='PRIVATE_SENTINEL'
        for row in r['personality']['juuni_unsei']['rows']:row['private_comment']='PRIVATE_SENTINEL'
        r.update({'memo':'MEMO_SENTINEL','person_id':'PERSON_SENTINEL','user_id':'OWNER_SENTINEL','calculation_details':'DETAIL_SENTINEL'})
        parts=unpack(render_xlsx(build_reading_report(FORM,r)))
        allbytes=b''.join(parts.values())
        for marker in (b'PRIVATE_SENTINEL',b'MEMO_SENTINEL',b'PERSON_SENTINEL',b'OWNER_SENTINEL',b'DETAIL_SENTINEL'):self.assertNotIn(marker,allbytes)
        self.assertNotIn('xl/calcChain.xml',parts)
        for path in ('xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml'):self.assertFalse(ET.fromstring(parts[path]).findall('.//s:f',NS))
        self.assertFalse(ET.fromstring(parts['xl/worksheets/sheet1.xml']).findall('.//s:v',NS))

    def test_yojin_hidden_sheet_and_rows(self):
        w=ET.fromstring(self.parts['xl/workbook.xml'])
        self.assertEqual([(x.get('name'),x.get('state','visible')) for x in w.findall('s:sheets/s:sheet',NS)],[('計算用','hidden'),('原本','visible')])
        sheet=ET.fromstring(self.parts['xl/worksheets/sheet2.xml'])
        for row in range(160,165):self.assertEqual(sheet.find(f"s:sheetData/s:row[@r='{row}']",NS).get('hidden'),'1')

    def test_template_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.xlsx';path.write_bytes(b'bad')
            with self.assertRaises(ReportError):render_xlsx(self.report,path)

    def test_tokens_owner_expiry_eviction_and_server_copy(self):
        now=[0];tokens=ExportTokens(ttl=10,capacity=1,clock=lambda:now[0])
        r=deepcopy(self.result);token=tokens.issue('one',FORM,r);r['yearly_overall']['comment']='CLIENT_CHANGED'
        self.assertNotEqual(tokens.get('one',token)[1]['yearly_overall']['comment'],'CLIENT_CHANGED')
        with self.assertRaises(ReportError):tokens.get('two',token)
        new=tokens.issue('one',FORM,self.result)
        with self.assertRaises(ReportError):tokens.get('one',token)
        now[0]=11
        with self.assertRaises(ReportError):tokens.get('one',new)

    def test_saved_snapshot_no_recalculation_owner_and_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=SQLiteHistoryRepository(Path(directory)/'history.sqlite3');service=HistoryService(repo)
            r=deepcopy(self.result);r['yearly_overall']['comment']='保存当時の正式コメント'
            row=service.create('one',{'input_snapshot':{'form':FORM},'result_snapshot':r,'memo':'SECRET_MEMO'})
            with patch('fortune_service.calculate_fortune',side_effect=AssertionError('must not recalculate')):
                filename,body=export_reading('one',{'reading_id':row['id']},repo)
            self.assertIn('保存当時の正式コメント'.encode(),b''.join(unpack(body).values()))
            self.assertNotIn(b'SECRET_MEMO',b''.join(unpack(body).values()))
            for marker in (row['id'],row['person_id'],row['group_id']):self.assertNotIn(marker.encode(),b''.join(unpack(body).values()))
            with self.assertRaises(HistoryError):export_reading('two',{'reading_id':row['id']},repo)
            repo.soft_delete('one',row['id'])
            with self.assertRaises(HistoryError):export_reading('one',{'reading_id':row['id']},repo)

    def test_arbitrary_client_result_rejected(self):
        for payload in ({'result_snapshot':self.result},{'export_token':'x','comment':'arbitrary'},{'reading_id':'x','user_id':'two'}):
            with self.assertRaises(ReportError):export_reading('one',payload)

    def test_api_new_reading_download_and_cross_owner(self):
        env={'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one'}
        with patch.dict('os.environ',env):
            status,headers,body=asyncio.run(api_call('POST','/api/fortune',FORM));self.assertEqual(status,200)
            token=json.loads(body)['excel_export_token']
            status,headers,body=asyncio.run(api_call('POST','/api/export/excel',{'export_token':token}))
            self.assertEqual(status,200);unpack(body)
            self.assertIn(b'filename*=UTF-8',headers[b'content-disposition']);self.assertEqual(headers[b'cache-control'],b'no-store')
        with patch.dict('os.environ',{**env,'FORTUNE_HISTORY_DEV_USER_ID':'two'}):
            self.assertEqual(asyncio.run(api_call('POST','/api/export/excel',{'export_token':token}))[0],404)

    def test_api_saved_deleted_and_other_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.sqlite3';repo=SQLiteHistoryRepository(path)
            row=HistoryService(repo).create('one',{'input_snapshot':{'form':FORM},'result_snapshot':self.result,'memo':'NEVER_EXPORT'})
            env={'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one','FORTUNE_HISTORY_DB_PATH':str(path)}
            with patch.dict('os.environ',env):
                status,headers,body=asyncio.run(api_call('POST','/api/export/excel',{'reading_id':row['id']}));self.assertEqual(status,200)
                self.assertNotIn(b'NEVER_EXPORT',b''.join(unpack(body).values()))
            with patch.dict('os.environ',{**env,'FORTUNE_HISTORY_DEV_USER_ID':'two'}):
                self.assertEqual(asyncio.run(api_call('POST','/api/export/excel',{'reading_id':row['id']}))[0],404)
            repo.soft_delete('one',row['id'])
            with patch.dict('os.environ',env):self.assertEqual(asyncio.run(api_call('POST','/api/export/excel',{'reading_id':row['id']}))[0],404)

    def test_api_fail_closed_and_invalid_body(self):
        with patch.dict('os.environ',{'FORTUNE_ENV':'production','FORTUNE_HISTORY_DEV_USER_ID':'one'}):
            self.assertEqual(asyncio.run(api_call('POST','/api/export/excel',{'reading_id':'x'}))[0],503)
        with patch.dict('os.environ',{'FORTUNE_ENV':'development','FORTUNE_HISTORY_DEV_USER_ID':'one'}):
            self.assertEqual(asyncio.run(api_call('POST','/api/export/excel',{'export_token':'x','text':'arbitrary'}))[0],422)


if __name__=='__main__':unittest.main(verbosity=2)
