"""Limited OOXML edits preserve the approved print layout and native drawing/chart objects.

Uses Python's standard library only, including on Linux. Never opens/saves with openpyxl.
"""
import hashlib
from io import BytesIO
from pathlib import Path
import re
from xml.dom import minidom
from zipfile import ZipFile, ZIP_DEFLATED
from report_data import ReadingReport, ReportError

TEMPLATE_SHA256 = "289b5d1093061487ba2e0e18bf6cd1c5c6056609daa31cbe0629e21489fa3b22"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "kanteisho.xlsx"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
X = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def children(node, local=None):
    return [n for n in node.childNodes if n.nodeType == n.ELEMENT_NODE and (local is None or n.localName == local)]


def first(node, local):
    return next(iter(children(node, local)), None)


def content(node):
    return "".join(n.data if n.nodeType in (n.TEXT_NODE,n.CDATA_SECTION_NODE) else content(n) for n in node.childNodes)


def replace_text(node, value):
    for n in list(node.childNodes): node.removeChild(n)
    node.appendChild(node.ownerDocument.createTextNode(str(value)))


def new(node, namespace, name, attrs=None, value=None):
    out = node.ownerDocument.createElementNS(namespace, name)
    for key, val in (attrs or {}).items(): out.setAttribute(key,str(val))
    if value is not None: out.appendChild(node.ownerDocument.createTextNode(str(value)))
    node.appendChild(out)
    return out


def serialize(doc):
    return doc.toxml(encoding="UTF-8")


class Styles:
    def __init__(self, doc):
        self.root = doc.documentElement
        self.fonts, self.borders, self.xfs = (first(self.root,k) for k in ("fonts","borders","cellXfs"))
        self.cache = {}

    def adjust(self, index, red=False, wrap=False, left=None, right=None):
        key = (index,red,wrap,left,right)
        if key in self.cache: return self.cache[key]
        xf = children(self.xfs)[index].cloneNode(True)
        font = children(self.fonts)[int(xf.getAttribute("fontId") or 0)].cloneNode(True)
        old = first(font,"color")
        if old is not None: font.removeChild(old)
        new(font,S,"color",{"rgb":"FFFF0000" if red else "FF000000"})
        self.fonts.appendChild(font); self.fonts.setAttribute("count",str(len(children(self.fonts))))
        xf.setAttribute("fontId",str(len(children(self.fonts))-1));xf.setAttribute("applyFont","1")
        alignment = first(xf,"alignment")
        if alignment is None: alignment = new(xf,S,"alignment")
        alignment.setAttribute("wrapText","1" if wrap else "0")
        alignment.setAttribute("shrinkToFit","0" if wrap else "1")
        xf.setAttribute("applyAlignment","1")
        if left is not None or right is not None:
            border = children(self.borders)[int(xf.getAttribute("borderId") or 0)].cloneNode(True)
            for side, heavy in (("left",left),("right",right)):
                if heavy is None: continue
                edge = first(border,side)
                if edge is None: edge = new(border,S,side)
                edge.setAttribute("style","thick" if heavy else "thin")
            self.borders.appendChild(border);self.borders.setAttribute("count",str(len(children(self.borders))))
            xf.setAttribute("borderId",str(len(children(self.borders))-1));xf.setAttribute("applyBorder","1")
        self.xfs.appendChild(xf);self.xfs.setAttribute("count",str(len(children(self.xfs))))
        value = len(children(self.xfs))-1
        self.cache[key] = value
        return value


def write_sheet(doc, values, styles, report, shared):
    data = first(doc.documentElement,"sheetData")
    rows = {int(r.getAttribute("r")):r for r in children(data,"row")}
    cells = {c.getAttribute("r"):c for row in rows.values() for c in children(row,"c")}
    # Keep approved printed static labels only. Discard legacy lookup data/formulas everywhere.
    for address, cell in cells.items():
        match = re.fullmatch(r"([A-Z]+)(\d+)",address)
        printed = len(match[1])==1 and match[1] <= "O" and int(match[2])<=68
        if printed and cell.getAttribute("t")=="s" and first(cell,"v") is not None:
            values.setdefault(address, shared[int(content(first(cell,"v")))])
        for n in list(children(cell)):
            if n.localName in ("f","v","is"):cell.removeChild(n)
        cell.removeAttribute("t") if cell.hasAttribute("t") else None
    for address, value in values.items():
        match = re.fullmatch(r"([A-Z]+)(\d+)",address)
        rownum = int(match[2]); row = rows.get(rownum)
        if row is None:
            row = doc.createElementNS(S,"row");row.setAttribute("r",str(rownum))
            following = next((r for num,r in sorted(rows.items()) if num > rownum),None)
            data.insertBefore(row,following);rows[rownum]=row
        cell = cells.get(address)
        if cell is None:
            cell = doc.createElementNS(S,"c");cell.setAttribute("r",address)
            def colnum(addr):
                total=0
                for char in re.match(r"[A-Z]+",addr)[0]:total=total*26+ord(char)-64
                return total
            following = next((c for c in children(row,"c") if colnum(c.getAttribute("r"))>colnum(address)),None)
            row.insertBefore(cell,following);cells[address]=cell
        if isinstance(value,(int,float)):
            new(cell,S,"v",value=f"{value:.15g}")
        else:
            cell.setAttribute("t","inlineStr")
            inline = new(cell,S,"is");new(inline,S,"t",{"xml:space":"preserve"},value)
        if address not in report.cells: continue
        col = ord(match[1])-ord('C') if len(match[1])==1 else -1
        red = 63<=rownum<=66 and col in report.kubou_months
        left = (col-1 in report.setsuboku_boundaries) if 56<=rownum<=59 and 0<col<=9 else None
        right = (col in report.setsuboku_boundaries) if 56<=rownum<=59 and 0<=col<9 else None
        cell.setAttribute("s",str(styles.adjust(int(cell.getAttribute("s") or 0),red,"\n" in str(value),left,right)))
    # Legacy conditional rules refer to the old Excel calculation, never to official values.
    for rule in list(children(doc.documentElement,"conditionalFormatting")):doc.documentElement.removeChild(rule)


def write_shapes(doc, texts):
    for shape in doc.getElementsByTagNameNS(X,"sp"):
        props = shape.getElementsByTagNameNS(X,"cNvPr")[0]
        key = props.getAttribute("name") if props.getAttribute("name") in texts else props.getAttribute("id")
        if key not in texts: continue
        body = first(shape,"txBody")
        paragraphs = children(body,"p")
        template = paragraphs[0]
        run = first(template,"r")
        for p in paragraphs:body.removeChild(p)
        for line in texts[key].split("\n"):
            p = template.cloneNode(True)
            for item in list(children(p)):
                if item.localName not in ("pPr","endParaRPr"):p.removeChild(item)
            r = run.cloneNode(True) if run is not None else p.ownerDocument.createElementNS(A,"a:r")
            for item in list(children(r)):
                if item.localName != "rPr":r.removeChild(item)
            new(r,A,"a:t",value=line)
            p.insertBefore(r,first(p,"endParaRPr"));body.appendChild(p)


def formula_values(formula, cells):
    match = re.fullmatch(r"'?原本'?!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?",formula)
    if not match:return None
    col,start,lastcol,end = match.groups()
    if lastcol and lastcol != col:return None
    addresses = [col+str(row) for row in range(int(start),int(end or start)+1)]
    return [cells[address] for address in addresses] if all(address in cells for address in addresses) else None


def write_charts(doc, cells):
    for node in list(doc.getElementsByTagName("*")):
        if node.localName not in ("numRef","strRef","datalabelsRange"): continue
        formula = first(node,"f")
        values = formula_values(content(formula),cells) if formula is not None else None
        if values is None: continue
        cache_name = {"numRef":"numCache","strRef":"strCache","datalabelsRange":"dlblRangeCache"}[node.localName]
        cache = first(node,cache_name)
        if cache is None:
            prefix = node.prefix+":" if node.prefix else ""
            cache = new(node,node.namespaceURI,prefix+cache_name)
        for item in list(children(cache)):
            if item.localName in ("pt","ptCount"):cache.removeChild(item)
        new(cache,C,"c:ptCount",{"val":len(values)})
        for i,value in enumerate(values):
            pt=new(cache,C,"c:pt",{"idx":i});new(pt,C,"c:v",value=f"{value:.15g}" if isinstance(value,(int,float)) else value)


def render_xlsx(report: ReadingReport, template_path=TEMPLATE_PATH):
    original = Path(template_path).read_bytes()
    if hashlib.sha256(original).hexdigest() != TEMPLATE_SHA256:
        raise ReportError("鑑定書テンプレートが承認版と一致しません。",503)
    with ZipFile(BytesIO(original)) as archive:
        files={info.filename:archive.read(info.filename) for info in archive.infolist()}
    strings_doc=minidom.parseString(files["xl/sharedStrings.xml"])
    strings=[]
    for si in children(strings_doc.documentElement,"si"):
        strings.append("".join(content(n) if n.localName=="t" else "".join(content(t) for t in children(n,"t")) for n in children(si) if n.localName in ("t","r")))
    style_doc=minidom.parseString(files["xl/styles.xml"]);styles=Styles(style_doc)
    sheet=minidom.parseString(files["xl/worksheets/sheet2.xml"])
    write_sheet(sheet,{**report.cells,**report.chart_cells},styles,report,strings)
    files["xl/worksheets/sheet2.xml"]=serialize(sheet)
    files["xl/styles.xml"]=serialize(style_doc)
    drawing=minidom.parseString(files["xl/drawings/drawing2.xml"])
    write_shapes(drawing,report.texts);files["xl/drawings/drawing2.xml"]=serialize(drawing)
    for index in range(1,6):
        name=f"xl/charts/chart{index}.xml";chart=minidom.parseString(files[name])
        write_charts(chart,report.chart_cells);files[name]=serialize(chart)
    # Preserve the hidden sheet and hidden Yojin layout, but ship no old computation or tables.
    calc=minidom.parseString(files["xl/worksheets/sheet1.xml"])
    for cell in calc.getElementsByTagNameNS(S,"c"):
        for n in list(children(cell)):
            if n.localName in ("f","v","is"):cell.removeChild(n)
        if cell.hasAttribute("t"):cell.removeAttribute("t")
    for local in ("drawing","conditionalFormatting","dataValidations"):
        for n in list(children(calc.documentElement,local)):calc.documentElement.removeChild(n)
    files["xl/worksheets/sheet1.xml"]=serialize(calc)
    files["xl/sharedStrings.xml"]=b'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="0" uniqueCount="0"/>'
    calc_rels=minidom.parseString(files["xl/worksheets/_rels/sheet1.xml.rels"])
    for rel in list(children(calc_rels.documentElement)):
        if rel.getAttribute("Type").endswith("/drawing"):calc_rels.documentElement.removeChild(rel)
    files["xl/worksheets/_rels/sheet1.xml.rels"]=serialize(calc_rels)
    removed={"xl/calcChain.xml","xl/drawings/drawing1.xml","xl/drawings/_rels/drawing1.xml.rels"}
    removed.update(name for name in files if name.startswith("xl/media/"))
    for name in removed:files.pop(name,None)
    types=minidom.parseString(files["[Content_Types].xml"])
    for entry in list(children(types.documentElement,"Override")):
        if entry.getAttribute("PartName").lstrip("/") in removed:types.documentElement.removeChild(entry)
    files["[Content_Types].xml"]=serialize(types)
    relations=minidom.parseString(files["xl/_rels/workbook.xml.rels"])
    for rel in list(children(relations.documentElement)):
        if rel.getAttribute("Type").endswith("/calcChain"):relations.documentElement.removeChild(rel)
    files["xl/_rels/workbook.xml.rels"]=serialize(relations)
    core=minidom.parseString(files["docProps/core.xml"])
    for node in children(core.documentElement):
        if node.localName in ("creator","lastModifiedBy","title","subject","description","keywords"):replace_text(node,"")
    files["docProps/core.xml"]=serialize(core)
    output=BytesIO()
    with ZipFile(output,"w",ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    return output.getvalue()
