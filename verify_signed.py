from pathlib import Path
import struct,plistlib,hashlib,json,shutil,aea
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from cryptography.hazmat.primitives.asymmetric import ec,rsa,padding
root=Path(__file__).resolve().parent

def chain_of(data):
 assert data[:4]==b'AEA1'
 size=struct.unpack_from('<I',data,8)[0]
 return [x509.load_der_x509_certificate(c) for c in plistlib.loads(data[12:12+size])['SigningCertificateChain']]
reference_sha256='63343abfb89a6a03ebb57e9b3f5fa7be7c4f5c756f3017b3a8c488c3653e9179'
results=[]
for base,title in [('Bill-v3.4.1','Bill v3.4.1'),('Phieu-Giao-Hang-v4.1.2','Phiếu Giao Hàng v4.1.2')]:
 original=plistlib.loads((root/'build'/f'{base}-unsigned.shortcut').read_bytes())
 file=root/'deliverables'/f'{base}.shortcut';data=file.read_bytes();chain=chain_of(data)
 assert hashlib.sha256(chain[-1].public_bytes(Encoding.DER)).hexdigest()==reference_sha256
 for child,parent in zip(chain,chain[1:]+chain[-1:]):
  key=parent.public_key();assert child.issuer==parent.subject
  if isinstance(key,ec.EllipticCurvePublicKey):key.verify(child.signature,child.tbs_certificate_bytes,ec.ECDSA(child.signature_hash_algorithm))
  elif isinstance(key,rsa.RSAPublicKey):key.verify(child.signature,child.tbs_certificate_bytes,padding.PKCS1v15(),child.signature_hash_algorithm)
  else:raise AssertionError('Unexpected signing key')
 plain=aea.decode(data,signature_pub=chain[0].public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo))
 actual=plistlib.loads(plain[plain.index(b'bplist00'):])
 differences={k for k in original.keys()|actual.keys() if original.get(k)!=actual.get(k)}
 assert differences<={'WFWorkflowName','WFWorkflowClientVersion'},differences
 assert original['WFWorkflowActions']==actual['WFWorkflowActions']
 target=root/'deliverables'/f'{title}.shortcut';shutil.copy2(file,target)
 results.append({'file':target.name,'nativeActions':len(actual['WFWorkflowActions']),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'signatureVerified':True,'certificateChainSignaturesVerified':True,'rootMatchesOriginal':True,'nativeActionsUnchanged':True,'iPhoneExecutionTested':False})
(root/'verification/signatures-v4.1.2.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False))
