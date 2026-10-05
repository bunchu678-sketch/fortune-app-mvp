"""Limited OOXML edits preserve the approved print layout and native drawing/chart objects.

Uses Python's standard library only, including on Linux. Never opens/saves with openpyxl.
"""
import hashlib
import math
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
GOGYO_CELLS = ("K6", "M8", "L12", "J12", "I8")
GOGYO_DRAWING_IDS = set(range(4, 24))
SECTION_GAP_PT = 7.5
SECTION_HEADING_ROWS = (25, 29, 34, 36, 43, 55, 60, 62, 67)
REPORT_PRINT_SCALE = 82
ADVICE_BOTTOM_INSET_PT = 6


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


def hide_gogyo_cell_text(sheet, styles):
    """Keep official source cell values, but draw their text inside the circles only."""
    formats = first(styles.root, "numFmts")
    if formats is None:
        formats = styles.root.ownerDocument.createElementNS(S, "numFmts")
        styles.root.insertBefore(formats, styles.fonts)
    format_id = max([163] + [int(n.getAttribute("numFmtId")) for n in children(formats)]) + 1
    new(formats, S, "numFmt", {"numFmtId": format_id, "formatCode": ";;;"})
    formats.setAttribute("count", str(len(children(formats))))
    for cell in sheet.getElementsByTagNameNS(S, "c"):
        if cell.getAttribute("r") not in GOGYO_CELLS:
            continue
        xf = children(styles.xfs)[int(cell.getAttribute("s"))].cloneNode(True)
        xf.setAttribute("numFmtId", str(format_id))
        xf.setAttribute("applyNumberFormat", "1")
        styles.xfs.appendChild(xf)
        cell.setAttribute("s", str(len(children(styles.xfs)) - 1))
    styles.xfs.setAttribute("count", str(len(children(styles.xfs))))


def apply_report_layout(sheet, drawing, styles):
    """Add half a line above headings without changing prose/font/body-box sizes."""
    merges = first(sheet.documentElement, "mergeCells")
    if not any(n.getAttribute("ref") == "D2:F2" for n in children(merges)):
        new(merges, S, "mergeCell", {"ref": "D2:F2"})
        merges.setAttribute("count", str(len(children(merges))))
    for row in sheet.getElementsByTagNameNS(S, "row"):
        rownum = int(row.getAttribute("r"))
        if rownum in SECTION_HEADING_ROWS:
            row.setAttribute("ht", f"{float(row.getAttribute('ht')) + SECTION_GAP_PT:g}")
            row.setAttribute("customHeight", "1")
        for cell in children(row, "c"):
            address = cell.getAttribute("r")
            if rownum not in SECTION_HEADING_ROWS and address not in ("C2", "D2"):
                continue
            xf = children(styles.xfs)[int(cell.getAttribute("s") or 0)].cloneNode(True)
            alignment = first(xf, "alignment")
            if alignment is None: alignment = new(xf, S, "alignment")
            alignment.setAttribute("vertical", "bottom" if rownum in SECTION_HEADING_ROWS else "center")
            if address in ("C2", "D2"): alignment.setAttribute("horizontal", "left")
            xf.setAttribute("applyAlignment", "1")
            styles.xfs.appendChild(xf)
            cell.setAttribute("s", str(len(children(styles.xfs)) - 1))
    styles.xfs.setAttribute("count", str(len(children(styles.xfs))))
    first(sheet.documentElement, "pageSetup").setAttribute("scale", str(REPORT_PRINT_SCALE))
    # Excel uses the row anchors; synchronize cached physical transforms too.
    for anchor in children(drawing.documentElement, "twoCellAnchor"):
        start = int(content(first(first(anchor, "from"), "row"))) + 1
        end = int(content(first(first(anchor, "to"), "row"))) + 1
        before = sum(SECTION_GAP_PT for row in SECTION_HEADING_ROWS if row < start) * 12700
        after = sum(SECTION_GAP_PT for row in SECTION_HEADING_ROWS if row < end) * 12700
        for transform in anchor.getElementsByTagNameNS(A, "xfrm"):
            off, ext = first(transform, "off"), first(transform, "ext")
            off.setAttribute("y", str(int(off.getAttribute("y")) + round(before)))
            ext.setAttribute("cy", str(int(ext.getAttribute("cy")) + round(after - before)))


def protect_advice_bottom_border(sheet, drawing, workbook):
    """Put the final cell border inside the print area, keeping the total page height."""
    rows = {int(r.getAttribute("r")): r for r in sheet.getElementsByTagNameNS(S, "row")}
    rows[68].setAttribute("ht", f"{float(rows[68].getAttribute('ht')) - ADVICE_BOTTOM_INSET_PT:g}")
    rows[69].setAttribute("ht", str(ADVICE_BOTTOM_INSET_PT))
    rows[69].setAttribute("hidden", "0")
    rows[69].setAttribute("customHeight", "1")
    # Row 69 is a cleared legacy row; keep the new printing gutter free of borders.
    for cell in children(rows[69], "c"):
        address = cell.getAttribute("r")
        if re.fullmatch(r"[A-O]69", address): cell.setAttribute("s", "0")
    for name in workbook.getElementsByTagNameNS(S, "definedName"):
        if name.getAttribute("name") == "_xlnm.Print_Area" and name.getAttribute("localSheetId") == "1":
            replace_text(name, "原本!$A$1:$O$69")
    for shape in drawing.getElementsByTagNameNS(X, "sp"):
        if shape.getElementsByTagNameNS(X, "cNvPr")[0].getAttribute("id") != "3": continue
        extent = first(first(first(shape, "spPr"), "xfrm"), "ext")
        extent.setAttribute("cy", str(int(extent.getAttribute("cy")) - ADVICE_BOTTOM_INSET_PT * 12700))


def polish_gogyo_layout(doc, report):
    """Update only the approved five-element drawing, in physical EMU coordinates."""
    anchors = {int(n.getAttribute("id")): n.parentNode.parentNode.parentNode
               for n in doc.getElementsByTagNameNS(X, "cNvPr")}
    frame = anchors[2].getElementsByTagNameNS(A, "xfrm")[0]
    off, ext = first(frame, "off"), first(frame, "ext")
    left, top = int(off.getAttribute("x")), int(off.getAttribute("y"))
    width, height = int(ext.getAttribute("cx")), int(ext.getAttribute("cy"))
    center = (left + width / 2, top + height * .55)
    orbit, radius = height * .36, height * .103
    points = [(center[0] + orbit * math.cos(math.radians(-90 + i * 72)),
               center[1] + orbit * math.sin(math.radians(-90 + i * 72))) for i in range(5)]

    def place(ident, x, y, w, h, flip_h=False, flip_v=False):
        old = anchors[ident]
        shape = next(n for n in children(old) if n.localName in ("sp", "cxnSp"))
        anchor = doc.createElementNS(X, "xdr:absoluteAnchor")
        new(anchor, X, "xdr:pos", {"x": round(x), "y": round(y)})
        new(anchor, X, "xdr:ext", {"cx": round(w), "cy": round(h)})
        anchor.appendChild(shape)
        anchor.appendChild(first(old, "clientData"))
        old.parentNode.replaceChild(anchor, old)
        anchors[ident] = anchor
        transform = first(first(shape, "spPr"), "xfrm")
        for name, enabled in (("flipH", flip_h), ("flipV", flip_v)):
            if enabled: transform.setAttribute(name, "1")
            elif transform.hasAttribute(name): transform.removeAttribute(name)
        first(transform, "off").setAttribute("x", str(round(x)))
        first(transform, "off").setAttribute("y", str(round(y)))
        first(transform, "ext").setAttribute("cx", str(round(w)))
        first(transform, "ext").setAttribute("cy", str(round(h)))
        return shape

    for i, ident in enumerate((20, 21, 22, 23, 19)):
        x, y = points[i]
        shape = place(ident, x-radius, y-radius, radius*2, radius*2)
        shape.getElementsByTagNameNS(X, "cNvPr")[0].setAttribute("name", f"Gogyo_Node_{i}")
        props = first(shape, "spPr")
        no_fill = first(props, "noFill")
        fill = doc.createElementNS(A, "a:solidFill")
        new(fill, A, "a:srgbClr", {"val": "FFFFFF"})
        props.replaceChild(fill, no_fill)
        body = first(shape, "txBody")
        for child in list(body.childNodes): body.removeChild(child)
        body_props = new(body, A, "a:bodyPr", {"anchor": "ctr", "anchorCtr": "1", "wrap": "none",
                         "lIns": "0", "tIns": "0", "rIns": "0", "bIns": "0"})
        new(body_props, A, "a:noAutofit")
        new(body, A, "a:lstStyle")
        paragraph = new(body, A, "a:p")
        new(paragraph, A, "a:pPr", {"algn": "ctr", "marL": "0", "marR": "0", "indent": "0"})
        run = new(paragraph, A, "a:r")
        run_props = new(run, A, "a:rPr", {"lang": "ja-JP", "sz": "1600", "b": "1"})
        new(new(run_props, A, "a:solidFill"), A, "a:srgbClr", {"val": "000000"})
        for font in ("latin", "ea"): new(run_props, A, "a:"+font, {"typeface": "游ゴシック"})
        new(run, A, "a:t", value=report.cells[GOGYO_CELLS[i]])

    # Five complete edges follow the official chart_order (a rotation of 木火土金水).
    # Both sets of arrows stop outside the node outlines; native line colours are preserved.
    for ident, source, target in [(9+i, i, (i+1)%5) for i in range(5)] + [
            (14,3,0), (15,0,2), (16,2,4), (17,1,3), (18,4,1)]:
        start, end = points[source], points[target]
        dx, dy = end[0]-start[0], end[1]-start[1]
        distance = math.hypot(dx, dy)
        clearance = radius + 7 * 12700
        sx, sy = start[0]+dx/distance*clearance, start[1]+dy/distance*clearance
        ex, ey = end[0]-dx/distance*clearance, end[1]-dy/distance*clearance
        shape = place(ident, min(sx,ex), min(sy,ey), abs(ex-sx), abs(ey-sy), ex<sx, ey<sy)
        shape.getElementsByTagNameNS(X, "cNvPr")[0].setAttribute(
            "name", f"Gogyo_{'Sheng' if ident<14 else 'Ke'}_{source}_{target}")
        geom = first(first(shape, "spPr"), "prstGeom")
        geom.setAttribute("prst", "straightConnector1")
        for adjustment in list(children(first(geom, "avLst"))): first(geom, "avLst").removeChild(adjustment)
        # Arc shapes become native connectors, so Excel renders a full line with its end arrow.
        if ident < 14:
            replacement = doc.createElementNS(X, "xdr:cxnSp")
            nv = new(replacement, X, "xdr:nvCxnSpPr")
            nv.appendChild(shape.getElementsByTagNameNS(X, "cNvPr")[0])
            new(nv, X, "xdr:cNvCxnSpPr")
            replacement.appendChild(first(shape, "spPr"))
            style = first(shape, "style")
            if style is not None: replacement.appendChild(style)
            shape.parentNode.replaceChild(replacement, shape)

    # Keep role labels outside node/arrow paths and inside the unchanged chart frame.
    label_height, label_width = 16*12700, 68*12700
    positions = {4:(points[0][0]-45*12700, points[0][1]-radius-18*12700, 90*12700),
                 5:(points[1][0]+radius+3*12700, points[1][1]-radius-12*12700, label_width),
                 6:(points[4][0]-radius-3*12700-label_width, points[4][1]-radius-12*12700, label_width),
                 7:(points[2][0]+radius+8*12700, points[2][1]-label_height/2, label_width),
                 8:(points[3][0]-radius-8*12700-label_width, points[3][1]-label_height/2, label_width)}
    for ident, (x, y, w) in positions.items(): place(ident, x, y, w, label_height)


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
    hide_gogyo_cell_text(sheet, styles)
    drawing=minidom.parseString(files["xl/drawings/drawing2.xml"])
    write_shapes(drawing,report.texts)
    apply_report_layout(sheet, drawing, styles)
    workbook=minidom.parseString(files["xl/workbook.xml"])
    protect_advice_bottom_border(sheet, drawing, workbook)
    files["xl/workbook.xml"]=serialize(workbook)
    files["xl/worksheets/sheet2.xml"]=serialize(sheet)
    files["xl/styles.xml"]=serialize(style_doc)
    polish_gogyo_layout(drawing, report)
    files["xl/drawings/drawing2.xml"]=serialize(drawing)
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
