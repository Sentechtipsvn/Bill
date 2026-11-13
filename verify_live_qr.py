"""Render the ACTUAL native workflow's HTML result and decode the live SVG QR.
The fixture contains VietQR's public example account; no private payment data.
"""
import sys,json,binascii,base64,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'project'))
from workflow import build
from test_workflow import files_for,qr_files,NOW,ROW,APP,record
from simulate_shortcut import Simulator,File,text
import ctypes,ctypes.util
from PIL import Image
import zxingcpp
root=Path(__file__).resolve().parent
svg=(root/'verification/vietqr-live.svg').read_text()
cfg=qr_files(name='QUY VAC XIN PHONG CHONG COVID',account='113366668888',bin='970415')
s=Simulator(build(),files=files_for(record(cash="665000",invoiceCode="HD3856"),extra=cfg),choices=[ROW,'🏦 Chuyển khoản / QR','📲 Hiện QR có số tiền'],now=NOW)
s.network_handler=lambda url:File('qr.svg',svg,NOW,540,640,'SVG')
s.run()
html=text(s.previews[0])
encoded=re.search(r'data:image/svg\+xml;base64,([^"]+)',html)[1]
assert base64.b64decode(encoded).decode()==svg
(root/'verification/qr-live-preview.html').write_text(html)
# Render the exact full SVG retained inside the native HTML via system librsvg.
# This verifies vector paths plus embedded artwork, not a logo-only extraction.
rsvg=ctypes.CDLL(ctypes.util.find_library('rsvg-2'))
pix=ctypes.CDLL(ctypes.util.find_library('gdk_pixbuf-2.0'))
go=ctypes.CDLL(ctypes.util.find_library('gobject-2.0'))
rsvg.rsvg_handle_new_from_data.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_void_p];rsvg.rsvg_handle_new_from_data.restype=ctypes.c_void_p
rsvg.rsvg_handle_get_pixbuf.argtypes=[ctypes.c_void_p];rsvg.rsvg_handle_get_pixbuf.restype=ctypes.c_void_p
pix.gdk_pixbuf_savev.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];pix.gdk_pixbuf_savev.restype=ctypes.c_int
go.g_object_unref.argtypes=[ctypes.c_void_p]
data=svg.encode();handle=rsvg.rsvg_handle_new_from_data(data,len(data),None);assert handle
image=rsvg.rsvg_handle_get_pixbuf(handle);assert image
assert pix.gdk_pixbuf_savev(image,str(root/'verification/qr-live-verified.png').encode(),b'png',None,None,None)
go.g_object_unref(image);go.g_object_unref(handle)

r=zxingcpp.read_barcode(Image.open(root/'verification/qr-live-verified.png'));assert r,'Full vector QR in HTML not decoded'
p=r.text
assert p[-8:-4]=='6304';assert f'{binascii.crc_hqx(p[:-4].encode(),0xffff):04X}'==p[-4:]
def tlv(s):
 d={};i=0
 while i<len(s):
  k=s[i:i+2];n=int(s[i+2:i+4]);d[k]=s[i+4:i+4+n];i+=4+n
 assert i==len(s);return d
v=tlv(p);beneficiary=tlv(tlv(v['38'])['01'])
assert beneficiary['00']=='970415';assert beneficiary['01']=='113366668888';assert v['54']=='1500000';assert v['53']=='704';assert tlv(v['62'])['08']=='THANH TOAN HD3856'
proof={'source':'Official VietQR QuickLink, public example account only','nativeWorkflowBase64KeepsFullSVG':True,'imageToTextCoercionAvoided':True,'fullSVGRasterized':True,'qrDecoded':True,'beneficiaryBIN':beneficiary['00'],'account':beneficiary['01'],'amount':v['54'],'currency':v['53'],'memo':tlv(v['62'])['08'],'crc16Verified':True,'iOSShortcutExecutionTested':False}
(root/'verification/qr-live-proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))

# Exercise the FIRST setup path with the real QR that omits amount and memo.
from workflow import OPTIONS
from test_workflow import files_for
from urllib.parse import urlparse,parse_qs
base_svg=(root/'verification/vietqr-base.svg').read_text()
setup=Simulator(build(),files=files_for(),choices=[OPTIONS,'🏦 Thiết lập QR',0,'✅ Tạo và lưu QR'],answers=['QUY VAC XIN PHONG CHONG COVID','113366668888','VietinBank'],now=NOW)
setup.network_handler=lambda url:File('base.svg',base_svg,NOW,540,640,'SVG')
setup.run()
config=json.loads(setup.files[APP+'QR/config.json'].data)
assert config['bin']=='970415'
params=parse_qs(urlparse(setup.network[0]).query,keep_blank_values=True)
assert 'amount' not in params and 'addInfo' not in params
base_html=text(setup.files[APP+'QR/'+config['baseFile']])
base_bytes=base64.b64decode(re.search(r'data:image/svg\+xml;base64,([^"]+)',base_html)[1])
assert base_bytes.decode()==base_svg
handle=rsvg.rsvg_handle_new_from_data(base_bytes,len(base_bytes),None);assert handle
image=rsvg.rsvg_handle_get_pixbuf(handle);assert image
assert pix.gdk_pixbuf_savev(image,str(root/'verification/qr-base-verified.png').encode(),b'png',None,None,None)
go.g_object_unref(image);go.g_object_unref(handle)
r=zxingcpp.read_barcode(Image.open(root/'verification/qr-base-verified.png'));assert r
payload=r.text;v=tlv(payload);bank=tlv(tlv(v['38'])['01'])
assert bank['00']=='970415' and bank['01']=='113366668888' and '54' not in v
assert f'{binascii.crc_hqx(payload[:-4].encode(),0xffff):04X}'==payload[-4:]
proof['firstSetupBaseQRVerified']=True;proof['baseHasNoAmount']=True
(root/'verification/qr-live-proof.json').write_text(json.dumps(proof,indent=2))
print(json.dumps({'firstSetupBaseQRVerified':True,'noAmountInBaseQR':True,'profileCached':True}))
