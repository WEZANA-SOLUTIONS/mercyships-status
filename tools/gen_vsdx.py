#!/usr/bin/env python3
"""Generate a movable-shape Visio (.vsdx) of the Mercy Ships donation flows.

Strategy: start from a known-good Visio package (the template bundled with the
`vsdx` library, which both Microsoft Visio and LibreOffice/libvisio accept),
keep all of its static parts (style sheets, the Dynamic Connector master,
document settings, windows, docProps) and replace only the page content and
page-size parts.

Each diagram node becomes an independent, freely-movable Visio Shape. The
arrows are Dynamic Connector instances (Master='2') glued to the shapes via
_WALKGLUE + _XFTRIGGER, so they re-route automatically when a box is dragged.
"""
import math
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = "/usr/local/lib/python3.11/dist-packages/vsdx/media/media.vsdx"
BUILD = os.path.join(HERE, "_vsdx_build")
OUT = os.path.join(ROOT, "donation_flows.vsdx")

# ---------------------------------------------------------------- diagram data
# node types: term (rounded terminator), proc (rectangle), dec (diamond)
ROWS = [
    ("W1 - Online donation (Qgiv)", [
        ("term", "Donor gives\non Qgiv"),
        ("proc", "Boomi MSUS\npushes txn"),
        ("proc", "Qgiv_Transaction__c\ncreated"),
        ("dec",  "Hourly Apex job\nQgivProcessScheduleJob"),
        ("proc", "Match to Contact\nQgiv_Contact_Match__c"),
        ("proc", "Create Opportunity\n+ Payment"),
        ("proc", "Allocate to GAU"),
    ]),
    ("W2 - Paper check (Check21)", [
        ("term", "Check arrives\nin mail"),
        ("proc", "Operator scans\nPayology / checkforce2"),
        ("proc", "Check record\n+ image"),
        ("dec",  "Scheduled batches\nVerify 20:45 / Returns 22:45"),
        ("proc", "Submit to Check21\nservice"),
        ("proc", "Create Opportunity\n+ Payment"),
        ("proc", "Allocate to GAU"),
    ]),
    ("W3 - Recurring schedule", [
        ("term", "RD agreement created\nnpe03__Recurring_Donation__c"),
        ("dec",  "NPSP\nschedule"),
        ("proc", "Spawns Opportunity\neach period"),
        ("proc", "Payment captured"),
        ("proc", "Allocation to GAU"),
        ("proc", "Receipting"),
    ]),
    ("W4 - Year-end receipt (EOY)", [
        ("term", "Gifts accumulated\nover year"),
        ("proc", "DonorFile /\nDonorFileDonation\nassembled"),
        ("proc", "Template resolved\nReceipt_Template_Mapping__c"),
        ("proc", "Dryad renders\nreceipt PDF"),
        ("proc", "DonorFileReceipt__c\ncreated"),
        ("proc", "Emailed / mailed\nto donor"),
    ]),
    ("W5 - New donor (constituent)", [
        ("term", "Inbound: web,\ncheck, manual, Lead"),
        ("dec",  "Duplicate check\nMSUS rules + dupcheck"),
        ("proc", "Create or update\nAccount + Contact"),
        ("proc", "Assign Unique Id /\nMSID"),
        ("proc", "Address record\ncreated"),
    ]),
]

# ---------------------------------------------------------------- layout (inches, origin bottom-left)
COL_X0, COL_DX = 2.1, 3.35
ROW_Y0, ROW_DY = 13.0, 2.6
PAGE_W, PAGE_H = 25.0, 15.0
W_PROC, H_PROC = 2.85, 1.15
W_TERM, H_TERM = 2.85, 1.00
W_DEC,  H_DEC  = 2.95, 1.50

def col_x(i): return COL_X0 + i * COL_DX
def row_y(r): return ROW_Y0 - r * ROW_DY

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))

# ---------------------------------------------------------------- geometry builders (shape-local inches)
def geom_rect(w, h):
    return (
        "<Section N='Geometry' IX='0'>"
        "<Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/>"
        "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
        "<Row T='RelMoveTo' IX='1'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row>"
        "<Row T='RelLineTo' IX='2'><Cell N='X' V='1'/><Cell N='Y' V='0'/></Row>"
        "<Row T='RelLineTo' IX='3'><Cell N='X' V='1'/><Cell N='Y' V='1'/></Row>"
        "<Row T='RelLineTo' IX='4'><Cell N='X' V='0'/><Cell N='Y' V='1'/></Row>"
        "<Row T='RelLineTo' IX='5'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row>"
        "</Section>"
    )

def geom_diamond(w, h):
    return (
        "<Section N='Geometry' IX='0'>"
        "<Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/>"
        "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
        "<Row T='RelMoveTo' IX='1'><Cell N='X' V='0'/><Cell N='Y' V='0.5'/></Row>"
        "<Row T='RelLineTo' IX='2'><Cell N='X' V='0.5'/><Cell N='Y' V='0'/></Row>"
        "<Row T='RelLineTo' IX='3'><Cell N='X' V='1'/><Cell N='Y' V='0.5'/></Row>"
        "<Row T='RelLineTo' IX='4'><Cell N='X' V='0.5'/><Cell N='Y' V='1'/></Row>"
        "<Row T='RelLineTo' IX='5'><Cell N='X' V='0'/><Cell N='Y' V='0.5'/></Row>"
        "</Section>"
    )

def geom_round(w, h):
    r = min(0.26, h / 2 - 0.02, w / 2 - 0.02)
    k = 0.70710678 * r
    rows, ix = [], [1]
    def add(s):
        rows.append(s.format(ix=ix[0])); ix[0] += 1
    add(f"<Row T='MoveTo' IX='{{ix}}'><Cell N='X' V='{r}'/><Cell N='Y' V='0'/></Row>")
    add(f"<Row T='LineTo' IX='{{ix}}'><Cell N='X' V='{w-r}'/><Cell N='Y' V='0'/></Row>")
    add(f"<Row T='EllipticalArcTo' IX='{{ix}}'><Cell N='X' V='{w}'/><Cell N='Y' V='{r}'/>"
        f"<Cell N='A' V='{w-r+k}'/><Cell N='B' V='{r-k}'/><Cell N='C' V='0'/><Cell N='D' V='1'/></Row>")
    add(f"<Row T='LineTo' IX='{{ix}}'><Cell N='X' V='{w}'/><Cell N='Y' V='{h-r}'/></Row>")
    add(f"<Row T='EllipticalArcTo' IX='{{ix}}'><Cell N='X' V='{w-r}'/><Cell N='Y' V='{h}'/>"
        f"<Cell N='A' V='{w-r+k}'/><Cell N='B' V='{h-r+k}'/><Cell N='C' V='0'/><Cell N='D' V='1'/></Row>")
    add(f"<Row T='LineTo' IX='{{ix}}'><Cell N='X' V='{r}'/><Cell N='Y' V='{h}'/></Row>")
    add(f"<Row T='EllipticalArcTo' IX='{{ix}}'><Cell N='X' V='0'/><Cell N='Y' V='{h-r}'/>"
        f"<Cell N='A' V='{r-k}'/><Cell N='B' V='{h-r+k}'/><Cell N='C' V='0'/><Cell N='D' V='1'/></Row>")
    add(f"<Row T='LineTo' IX='{{ix}}'><Cell N='X' V='0'/><Cell N='Y' V='{r}'/></Row>")
    add(f"<Row T='EllipticalArcTo' IX='{{ix}}'><Cell N='X' V='{r}'/><Cell N='Y' V='0'/>"
        f"<Cell N='A' V='{r-k}'/><Cell N='B' V='{r-k}'/><Cell N='C' V='0'/><Cell N='D' V='1'/></Row>")
    return ("<Section N='Geometry' IX='0'>"
            "<Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/>"
            "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>" + "".join(rows) + "</Section>")

# line / fill colours per node type (hex; matches the source diagram)
STYLE = {
    "term": ("#2E5FA3", "#FFFFFF", 0.75),
    "proc": ("#2E75B6", "#FFFFFF", 1.0),
    "dec":  ("#C45911", "#FFFFFF", 1.0),
}

def node_shape(sid, kind, text, cx, cy):
    lc, fc, lw = STYLE[kind]
    if kind == "dec":
        w, h, geom = W_DEC, H_DEC, geom_diamond(W_DEC, H_DEC)
    elif kind == "term":
        w, h, geom = W_TERM, H_TERM, geom_round(W_TERM, H_TERM)
    else:
        w, h, geom = W_PROC, H_PROC, geom_rect(W_PROC, H_PROC)
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"<Cell N='PinX' V='{cx}'/><Cell N='PinY' V='{cy}'/>"
        f"<Cell N='Width' V='{w}'/><Cell N='Height' V='{h}'/>"
        f"<Cell N='LocPinX' V='{w/2}' F='Width*0.5'/><Cell N='LocPinY' V='{h/2}' F='Height*0.5'/>"
        f"<Cell N='Angle' V='0'/><Cell N='FlipX' V='0'/><Cell N='FlipY' V='0'/>"
        f"<Cell N='ResizeMode' V='0'/><Cell N='ObjType' V='1'/>"
        f"<Cell N='LineColor' V='{lc}'/><Cell N='LineWeight' V='{lw/72}'/>"
        f"<Cell N='FillForegnd' V='{fc}'/>"
        f"<Cell N='VerticalAlign' V='1'/>"
        f"{geom}"
        f"<Section N='Character'><Row IX='0'><Cell N='Size' V='0.11'/>"
        f"<Cell N='Color' V='#1A1A1A'/></Row></Section>"
        f"<Section N='Paragraph'><Row IX='0'><Cell N='HorzAlign' V='1'/></Row></Section>"
        f"<Text>{esc(text)}</Text>"
        f"</Shape>"
    )

def label_shape(sid, text, cx, cy):
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"<Cell N='PinX' V='{cx}'/><Cell N='PinY' V='{cy}'/>"
        f"<Cell N='Width' V='4.5'/><Cell N='Height' V='0.3'/>"
        f"<Cell N='LocPinX' V='2.25' F='Width*0.5'/><Cell N='LocPinY' V='0.15' F='Height*0.5'/>"
        f"<Cell N='Angle' V='0'/><Cell N='ObjType' V='1'/>"
        f"<Cell N='LinePattern' V='0'/><Cell N='FillPattern' V='0'/>"
        f"<Section N='Geometry' IX='0'><Cell N='NoFill' V='1'/><Cell N='NoLine' V='1'/>"
        f"<Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
        f"<Row T='RelMoveTo' IX='1'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row>"
        f"<Row T='RelLineTo' IX='2'><Cell N='X' V='1'/><Cell N='Y' V='0'/></Row></Section>"
        f"<Section N='Character'><Row IX='0'><Cell N='Size' V='0.1'/>"
        f"<Cell N='Color' V='#7F7F7F'/></Row></Section>"
        f"<Section N='Paragraph'><Row IX='0'><Cell N='HorzAlign' V='1'/></Row></Section>"
        f"<Text>{esc(text)}</Text>"
        f"</Shape>"
    )

def connector_shape(sid, fid, tid, bx, by, ex, ey):
    bg = "_WALKGLUE(BegTrigger,EndTrigger,WalkPreference)"
    eg = "_WALKGLUE(EndTrigger,BegTrigger,WalkPreference)"
    return (
        f"<Shape ID='{sid}' NameU='Dynamic connector' Name='Dynamic connector' "
        f"Type='Shape' Master='2'>"
        f"<Cell N='PinX' V='{(bx+ex)/2}' F='Inh'/><Cell N='PinY' V='{(by+ey)/2}' F='Inh'/>"
        f"<Cell N='Width' V='{ex-bx}' F='GUARD(EndX-BeginX)'/>"
        f"<Cell N='Height' V='{ey-by}' F='GUARD(EndY-BeginY)'/>"
        f"<Cell N='LocPinX' V='{(ex-bx)/2}' F='Inh'/><Cell N='LocPinY' V='{(ey-by)/2}' F='Inh'/>"
        f"<Cell N='BeginX' V='{bx}' F='{bg}'/><Cell N='BeginY' V='{by}' F='{bg}'/>"
        f"<Cell N='EndX' V='{ex}' F='{eg}'/><Cell N='EndY' V='{ey}' F='{eg}'/>"
        f"<Cell N='LayerMember' V='0'/>"
        f"<Cell N='BegTrigger' V='2' F='_XFTRIGGER(Sheet.{fid}!EventXFMod)'/>"
        f"<Cell N='EndTrigger' V='2' F='_XFTRIGGER(Sheet.{tid}!EventXFMod)'/>"
        f"<Cell N='ShapeRouteStyle' V='16'/><Cell N='ConFixedCode' V='6'/>"
        f"<Cell N='ConLineRouteExt' V='1'/>"
        f"<Section N='Geometry' IX='0'>"
        f"<Row T='MoveTo' IX='1'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row>"
        f"<Row T='LineTo' IX='2'><Cell N='X' V='{ex-bx}'/><Cell N='Y' V='{ey-by}'/></Row>"
        f"</Section>"
        f"</Shape>"
    )

# ---------------------------------------------------------------- assemble page content
shapes, connects = [], []
sid = 1
node_ids = []
for r, (label, nodes) in enumerate(ROWS):
    cy = row_y(r)
    ids = []
    for c, (kind, text) in enumerate(nodes):
        cx = col_x(c)
        shapes.append(node_shape(sid, kind, text, cx, cy))
        w = W_DEC if kind == "dec" else (W_TERM if kind == "term" else W_PROC)
        ids.append((sid, kind, cx, cy, w)); sid += 1
    node_ids.append(ids)

for r, (label, nodes) in enumerate(ROWS):
    cy = row_y(r) + (ROW_DY / 2) - 0.35
    shapes.append(label_shape(sid, label, col_x(2), cy)); sid += 1

for ids in node_ids:
    for (fid, fk, fcx, fcy, fw), (tid, tk, tcx, tcy, tw) in zip(ids, ids[1:]):
        bx, by = fcx + fw / 2, fcy
        ex, ey = tcx - tw / 2, tcy
        shapes.append(connector_shape(sid, fid, tid, bx, by, ex, ey))
        connects.append(
            f"<Connect FromSheet='{sid}' FromCell='BeginX' FromPart='9' "
            f"ToSheet='{fid}' ToCell='PinX' ToPart='3'/>")
        connects.append(
            f"<Connect FromSheet='{sid}' FromCell='EndX' FromPart='12' "
            f"ToSheet='{tid}' ToCell='PinX' ToPart='3'/>")
        sid += 1

page1 = (
    "<?xml version='1.0' encoding='utf-8' ?>\n"
    "<PageContents xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
    "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
    "xml:space='preserve'>"
    "<Shapes>" + "".join(shapes) + "</Shapes>"
    "<Connects>" + "".join(connects) + "</Connects>"
    "</PageContents>"
)

pages = (
    "<?xml version='1.0' encoding='utf-8' ?>\n"
    "<Pages xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
    "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
    "xml:space='preserve'>"
    f"<Page ID='0' NameU='Donation flows' Name='Donation flows' ViewScale='-1' "
    f"ViewCenterX='{PAGE_W/2}' ViewCenterY='{PAGE_H/2}'>"
    "<PageSheet LineStyle='0' FillStyle='0' TextStyle='0'>"
    f"<Cell N='PageWidth' V='{PAGE_W}'/><Cell N='PageHeight' V='{PAGE_H}'/>"
    "<Cell N='ShdwOffsetX' V='0.1181102362204724'/>"
    "<Cell N='ShdwOffsetY' V='-0.1181102362204724'/>"
    "<Cell N='PageScale' V='0.03937007874015748' U='MM'/>"
    "<Cell N='DrawingScale' V='0.03937007874015748' U='MM'/>"
    "<Cell N='DrawingSizeType' V='3'/><Cell N='DrawingScaleType' V='0'/>"
    "<Cell N='InhibitSnap' V='0'/><Cell N='DrawingResizeType' V='1'/>"
    "<Cell N='PageShapeSplit' V='1'/>"
    "<Section N='Layer'><Row IX='0'><Cell N='Name' V='Connector'/>"
    "<Cell N='Color' V='255'/><Cell N='Status' V='0'/><Cell N='Visible' V='1'/>"
    "<Cell N='Print' V='1'/><Cell N='Active' V='0'/><Cell N='Lock' V='0'/>"
    "<Cell N='Snap' V='1'/><Cell N='Glue' V='1'/><Cell N='NameUniv' V='Connector'/>"
    "<Cell N='ColorTrans' V='0'/></Row></Section>"
    "</PageSheet><Rel r:id='rId1'/></Page></Pages>"
)

# ---------------------------------------------------------------- build package from template
if os.path.exists(BUILD):
    shutil.rmtree(BUILD)
os.makedirs(BUILD)
with zipfile.ZipFile(TEMPLATE) as z:
    names = z.namelist()
    z.extractall(BUILD)

with open(os.path.join(BUILD, "visio/pages/page1.xml"), "w", encoding="utf-8") as f:
    f.write(page1)
with open(os.path.join(BUILD, "visio/pages/pages.xml"), "w", encoding="utf-8") as f:
    f.write(pages)

# the template page1.xml.rels references shape data / images we no longer use;
# strip it to an empty relationships part so nothing dangles.
p1rels = os.path.join(BUILD, "visio/pages/_rels/page1.xml.rels")
if os.path.exists(p1rels):
    with open(p1rels, "w", encoding="utf-8") as f:
        f.write("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                "<Relationships xmlns='http://schemas.openxmlformats.org/"
                "package/2006/relationships'/>")

if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name in names:
        z.write(os.path.join(BUILD, name), name)

shutil.rmtree(BUILD)
print("wrote", OUT)
print("nodes + labels + connectors =", sid - 1)
