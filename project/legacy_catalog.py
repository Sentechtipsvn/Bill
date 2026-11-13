"""Index legacy invoice filenames once, without reading or decoding photos."""
from shortcut_builder import ref,token
from shared import DEFAULTS,field,MONEY

NAME_PATTERN=r'\A(.+)\s+-\s+([0-9][0-9., \u00a0]*)(?:\s*(?:₫|đ|VND))?(?:\s*·\s*([0-9][0-9_-]{5,40}))?\s*\z'
KEY_PATTERN=r'·\s*([0-9]{14,24}-[0-9]{6})\.png\z'
MARKER='_legacyFilenamesV411'

def index_legacy(b):
 with b.if_(b.get(ref('Ledger'),MARKER),'empty'):
  # Existing financial records and sidecar aliases retain their identity.
  b.dictionary(var='KnownLegacyNames');b.set('LegacyAdded','0')
  with b.each(b.keys(ref('Ledger')),'KnownLegacyID'):
   with b.if_(b.match(ref('KnownLegacyID'),r'\A[a-f0-9]{64}\z')):
    b.parse(b.get(ref('Ledger'),ref('KnownLegacyID')),'KnownLegacyRecord')
    name=field('KnownLegacyRecord','filename')
    with b.if_(name):b.put(ref('KnownLegacyNames'),b.hash(name),ref('KnownLegacyID'),'KnownLegacyNames')
  entries=b.add('file.getfoldercontents',WFFolder=ref('ImagesFolder'),Recursive=False)
  with b.each(entries,'LegacyCatalogFile'):
   b.set('LegacyCatalogName',b.add('getitemname',WFInput=ref('LegacyCatalogFile')))
   with b.if_(b.match(ref('LegacyCatalogName'),r'(?i)\.(?:png|jpe?g|heic|heif|webp)\z'),'empty'):
    ext=b.add('properties.files',WFInput=ref('LegacyCatalogFile'),WFContentItemPropertyName='File Extension')
    with b.if_(ext):b.text(token(ref('LegacyCatalogName'),'.',ext),'LegacyCatalogName')
   b.hash(ref('LegacyCatalogName'),'LegacyCatalogID')
   with b.if_(b.get(ref('KnownLegacyNames'),ref('LegacyCatalogID')),'empty'):
    base=b.replace(ref('LegacyCatalogName'),r'(?i)\.(?:png|jpe?g|heic|heif|webp)\z','')
    matches=b.match(base,NAME_PATTERN)
    with b.if_(matches):
     matched=b.first(matches)
     customer=b.add('text.match.getgroup',matches=matched,WFGetGroupType='Group At Index',WFGroupIndex=1)
     customer=b.replace(customer,r'^\s+|\s+$','')
     amount=b.add('text.match.getgroup',matches=matched,WFGetGroupType='Group At Index',WFGroupIndex=2)
     amount=b.replace(amount,r'[^0-9]','')
     with b.if_(b.match(customer,r'\p{L}')):
      with b.if_(b.match(amount,MONEY)):
       key=b.match(ref('LegacyCatalogName'),KEY_PATTERN)
       with b.if_(key):
        stamp=b.add('text.match.getgroup',matches=b.first(key),WFGetGroupType='Group At Index',WFGroupIndex=1)
        b.hash(b.text(token('sen-bill-v1:',stamp)),'LegacyCatalogID')
       with b.if_(b.get(ref('Ledger'),ref('LegacyCatalogID')),'empty'):
        b.set('LegacyCreated',ref('NowISO'));b.set('LegacyMonth',ref('CurrentMonth'))
        created=b.add('properties.files',WFInput=ref('LegacyCatalogFile'),WFContentItemPropertyName='Creation Date')
        with b.if_(created):
         b.fmtdate(created,"yyyy-MM-dd'T'HH:mm:ssXXX",'LegacyCreated');b.fmtdate(created,'yyyy-MM','LegacyMonth')
        b.dictionary({**DEFAULTS,'id':ref('LegacyCatalogID'),'filename':ref('LegacyCatalogName'),'name':customer,'total':amount,'createdAt':ref('LegacyCreated'),'createdMonth':ref('LegacyMonth')},'LegacyCatalogRecord')
        b.put(ref('Ledger'),ref('LegacyCatalogID'),b.text(ref('LegacyCatalogRecord')),'Ledger')
        b.math(ref('LegacyAdded'),'+1',var='LegacyAdded');b.set('Dirty','1')
  with b.if_(ref('LegacyAdded'),'gt',0):b.put(ref('Ledger'),'_sourceMigrated','','Ledger')
  b.put(ref('Ledger'),MARKER,'1','Ledger');b.set('Dirty','1')
