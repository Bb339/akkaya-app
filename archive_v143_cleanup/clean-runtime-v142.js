/* v142 clean runtime: approved plan, notification bell and stable message docks */
(function(){
  if(window.__akkayaCleanRuntimeV142) return;
  window.__akkayaCleanRuntimeV142 = true;
  window.__disableLegacyFarmerPatternForcesV118 = true;

  const APPROVED_KEY = 'sazlica_approved_recommendations_v103';
  const PLAN_OPEN_KEY = 'akkayaApprovedPlanOpenV142';
  const esc = value => (typeof escapeHtml === 'function')
    ? escapeHtml(String(value ?? ''))
    : String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const num = (value, fallback=0) => (typeof safeNum === 'function') ? safeNum(value, fallback) : (Number.isFinite(Number(value)) ? Number(value) : fallback);
  const fmt = value => Math.round(num(value, 0)).toLocaleString('tr-TR');
  const money = value => `${fmt(value)} TL`;
  const norm = value => String(value || '').toLocaleUpperCase('tr-TR').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/İ/g,'I');
  const pretty = value => (typeof prettyCropName === 'function') ? prettyCropName(value) : String(value || '').trim();

  const CROP_GUIDES = [
    {
      keys:['PATATES'], label:'Patates', waterClass:'Yuksek ama yonetilebilir', gdd:'Yaklasik 1.250-1.600 GDD; yumru baglama ve yumru buyutme doneminde stres esigi dusuktur.',
      irrigation:'Damla sulama veya iyi ayarli yagmurlama. Karik/salma yerine basincli sistem onerilir; yumru baglama-yumru irilesme doneminde toprak nemi %50 tuketimin altina dusurulmemelidir.',
      soil:'Iyi drene, havalanan, tassiz ve tavli toprak. Sonbaharda derin surum; ilkbaharda kesek kirma, organik madde ve taban gubresi.',
      calendar:[['Subat-Mart','Toprak analizi, sertifikali tohumluk, munavebe ve depo/pazar plani.'],['Nisan','Dikim, sirt hazirligi, cikis oncesi yabanci ot kontrolu.'],['Mayis-Haziran','Bogaz doldurma, ilk damla/yagmurlama programi, azot takibi.'],['Temmuz-Agustos','Yumru buyutme, mildiyo-erken yaniklik ve bocek izlemesi, su stresi kontrolu.'],['Eylul-Ekim','Hasat, zedelenmeyi azaltma, depo havalandirmasi ve satis partisi plani.']],
      risks:['Mildiyo','Erken yaniklik','Patates bocegi','Tel kurdu','Nematod','Depo curuklukleri'],
      incentive:'Patates Nigde icin guclu urundur; tesvik yalnizca damla/yagmurlama, sertifikali tohum, sozlesmeli uretim ve dortlu munavebe sartiyla onerilir.'
    },
    {
      keys:['KURU FASULYE','FASULYE','BARBUNYA'], label:'Kuru fasulye / barbunya', waterClass:'Orta', gdd:'Yaklasik 900-1.200 GDD; ciceklenme ve bakla baglama donemi kritik su donemidir.',
      irrigation:'Damla sulama en dengeli secenek; yagmurlamada ciceklenme doneminde yaprak islakligi ve hastalik riski izlenmelidir.',
      soil:'Tavli, drenaji iyi, kaymak baglamayan toprak. Asiri azottan kacin; bakteri asilamasi ve fosfor-potasyum dengesi onemlidir.',
      calendar:[['Nisan','Toprak hazirligi, tohum ve bakteri asisi plani.'],['Mayis','Ekim; sira arasi capaya uygun mesafe.'],['Haziran','Capa, yabanci ot ve ilk sulama.'],['Temmuz','Ciceklenme/bakla baglama, antraknoz ve kirmizi orumcek kontrolu.'],['Agustos-Eylul','Hasat nemi, harman, kalite siniflama ve alici plani.']],
      risks:['Antraknoz','Kok curuklugu','Yaprak biti','Kirmizi orumcek','Bakteriyel yaniklik'],
      incentive:'Nigde kuru fasulye/barbunya merkezi oldugu icin tohum destegi, alim garantisi ve damla sulama paketiyle tesvik edilebilir.'
    },
    {
      keys:['NOHUT'], label:'Nohut', waterClass:'Dusuk', gdd:'Yaklasik 850-1.150 GDD; serin baslangic ve kuru hasat donemi avantaj saglar.',
      irrigation:'Kuru kosula dayaniklidir; cikis ve ciceklenme oncesi destek sulama yeterli olabilir. Fazla sulama kok hastaligini artirir.',
      soil:'Drenaji iyi, asiri tuzlu olmayan ve agir taban suyu olmayan alanlar. Azot baglama etkisi nedeniyle munavebede guclu ara urundur.',
      calendar:[['Subat-Mart','Tohumluk ve antraknoz dayanimi secimi.'],['Mart-Nisan','Ekim, merdane ve cikis kontrolu.'],['Mayis','Yabanci ot ve antraknoz izlemesi.'],['Haziran','Bakla dolumu; gerekirse tek destek sulama.'],['Temmuz-Agustos','Hasat, nem kontrolu ve dane siniflama.']],
      risks:['Antraknoz','Yesil kurt','Yaprak biti','Kok curuklugu'],
      incentive:'Su tasarrufu ve atil/kuru alanlari uretime alma etkisi yuksek; gelir farki primi ve sertifikali tohum destegi icin en uygun urunlerden biridir.'
    },
    {
      keys:['MERCIMEK'], label:'Mercimek', waterClass:'Cok dusuk', gdd:'Yaklasik 800-1.100 GDD; kisa sezon ve dusuk su tuketimi avantajdir.',
      irrigation:'Genellikle yagisa bagli; kurak ilkbaharda tek destek sulama uygulanabilir.',
      soil:'Iyi drene tarla, erken ekim, yabanci otla erken mucadele. Tahil sonrasi munavebede toprak azotuna katki saglar.',
      calendar:[['Subat-Mart','Ekim hazirligi ve sertifikali tohum.'],['Mart-Nisan','Cikis ve yabanci ot kontrolu.'],['Mayis','Ciceklenme, hastalik gozlemi.'],['Haziran-Temmuz','Hasat ve harman.']],
      risks:['Antraknoz','Pas','Yaprak biti','Yabanci ot baskisi'],
      incentive:'Kurak yil tamponu olarak dusuk su primi ve tohum destegiyle tesvik edilebilir.'
    },
    {
      keys:['KIMYON'], label:'Kimyon', waterClass:'Dusuk-Orta', gdd:'Yaklasik 1.000-1.300 GDD; kurak ve serin-gecisli alanlarda pazar degeri yuksektir.',
      irrigation:'Az ama zamaninda destek sulama; asiri nem mantari hastalik riskini artirir.',
      soil:'Ince hazirlanmis, iyi drene ve yabanci ottan temiz tarla. Cikis yavas oldugu icin erken donem ot kontrolu kritiktir.',
      calendar:[['Subat-Mart','Ince tohum yatagi ve pazar baglantisi.'],['Mart-Nisan','Ekim, cikis ve yabanci ot kontrolu.'],['Mayis-Haziran','Ciceklenme, hastalik takibi ve sinirli destek sulama.'],['Temmuz','Hasat, kurutma ve kalite siniflama.']],
      risks:['Kok curuklugu','Kulleme','Yabanci ot rekabeti','Hasatta dane dokulmesi'],
      incentive:'Dusuk su + yuksek katma deger dengesi nedeniyle nohut/mercimek ile kombinasyonda gelir farki telafi tesviki icin uygundur.'
    },
    {
      keys:['ARPA','BUGDAY','BUĞDAY','CAVDAR','ÇAVDAR','TRITIKALE','YULAF'], label:'Serin iklim tahili', waterClass:'Dusuk-Orta', gdd:'Yaklasik 1.600-2.200 GDD; kardeslenme ve basaklanma donemi izlenir.',
      irrigation:'Kislik ekimde yagis ana kaynaktir. Basaklanma oncesi tek destek sulama verimi korur; su kisitinda cavdar/arpa daha guvenlidir.',
      soil:'Sonbaharda tavli ekim, dengeli fosfor ve azot bolunmesi. Erozyon ve ruzgar riskine karsi aniz/ortu korunmali.',
      calendar:[['Eylul-Ekim','Toprak hazirligi ve ekim.'],['Kasim-Mart','Cikis, kardeslenme ve gubreleme.'],['Nisan-Mayis','Basaklanma, pas/kulleme takibi ve gerekirse destek sulama.'],['Haziran-Temmuz','Hasat, saman/yem degeri ve munavebe plani.']],
      risks:['Sari pas','Kulleme','Sune-kimil','Yabanci ot','Kurak ilkbahar'],
      incentive:'Cavdar/arpa + fig gibi dusuk su desenleri sosyal su faydasi yuksek seceneklerdir; yem acigini da azaltir.'
    },
    {
      keys:['FIĞ','FİĞ','YEM','YONCA'], label:'Yem bitkisi / fig', waterClass:'Orta', gdd:'Fig icin yaklasik 900-1.200 GDD; yonca cok yillik oldugu icin bicim aralarina gore yonetilir.',
      irrigation:'Figde sinirli destek sulama; yoncada bicim sonrasi sulama verimi belirler. Salma yerine yagmurlama/damla tercih edilir.',
      soil:'Toprak organik maddesini destekler; tahil ve sebze munavebesi icin iyi ara urundur.',
      calendar:[['Eylul-Ekim','Kislik fig ekimi veya yonca tesis hazirligi.'],['Mart-Nisan','Gelisim ve yabanci ot kontrolu.'],['Mayis-Haziran','Bicim/hasat; sonraki urun icin toprak nemi koruma.']],
      risks:['Yaprak biti','Kok bogazi hastaliklari','Bicim zamani kaybi'],
      incentive:'Hayvancilik baglantisi ve toprak koruma etkisi nedeniyle dusuk su tahillariyla kombinasyonda desteklenebilir.'
    },
    {
      keys:['ELMA','KIRAZ','ARMUT','CEVIZ','CEVİZ','BADEM'], label:'Meyve bahcesi', waterClass:'Orta-Yuksek', gdd:'Tur ve ceside gore degisir; tomurcuk kabarmasi, ciceklenme ve meyve irilesme donemleri kritik izlenir.',
      irrigation:'Damla sulama, malc/ortu ve tensiyometre ile yonetim. Asiri sulama kalite ve hastalik riskini artirir.',
      soil:'Cok yillik yatirim oldugu icin ana urun korunur; iyilestirme sulama, don riski, budama, besleme ve sira arasi yonetimden gelir.',
      calendar:[['Ocak-Subat','Budama, kis bakimi, don plani.'],['Mart-Nisan','Ciceklenme, don uyarisi, ari ve ilaclama plani.'],['Mayis-Haziran','Meyve seyreltme, damla sulama ve besleme.'],['Temmuz-Eylul','Hasat ceside gore planlanir; kalite siniflama.'],['Ekim-Kasim','Sonbahar gubreleme ve sulama kapatma.']],
      risks:['Karaleke','Ic kurdu','Ates yanikligi','Don','Gunes yanikligi','Depo hastaliklari'],
      incentive:'Nigde elma/kirazda gucludur; yeni sok-dik yerine damla, sensor, file/don ve paketleme kalitesi tesviki daha dogru olur.'
    },
    {
      keys:['DOMATES','BIBER','BİBER','MARUL','LAHANA','SOGAN','SOĞAN','SARIMSAK','KABAK'], label:'Sebze deseni', waterClass:'Orta-Yuksek', gdd:'Sebzede urun turune gore 800-1.600 GDD; ciceklenme, bas baglama veya yumru/sogan irilesme donemi kritiktir.',
      irrigation:'Damla sulama ve gubreleme birlikte yonetilmeli; yaprak islakligini azaltmak hastalik riskini dusurur.',
      soil:'Iyi hazirlanmis tohum yatagi, organik madde, drenaj ve pazar/iscilik plani gerekir.',
      calendar:[['Mart-Nisan','Fide/tohum, damla hatlari ve malc hazirligi.'],['Mayis','Dikim/ekim, can suyu ve ilk capalar.'],['Haziran-Temmuz','Besleme, hastalik-zararli takibi, duzenli sulama.'],['Agustos-Ekim','Hasat, siniflama, pazar sevki.']],
      risks:['Mildiyo','Kulleme','Kirmizi orumcek','Yaprak biti','Bakteriyel hastaliklar','Pazar fiyat dalgalanmasi'],
      incentive:'Sebzede tesvik su kisiti ve pazar garantisi ile sinirlandirilmali; damla sulama, sozlesmeli satis ve hastalik takibi sarti aranmali.'
    }
  ];

  const INCENTIVE_ROWS = [
    {title:'Nohut + mercimek / dusuk su baklagil hatti', rate:'%60-75 tohum + gelir farki primi', why:'Kurak/kisitli su kosullarinda uretimi surdurur, topraga azot katkisi saglar ve atil alani uretime alir.', social:'Daha az sulama baskisi, daha genis ciftci katilimi ve gida guvenligi.'},
    {title:'Kuru fasulye / barbunya', rate:'%50 damla + %60-75 sertifikali tohum', why:'Nigde guclu uretim merkezidir; yerli alim ve sozlesmeli pazarla ciftci guveni artar.', social:'Yerel marka, paketleme ve ticaret degeri yaratir.'},
    {title:'Kimyon + nohut/mercimek kombinasyonu', rate:'%35-45 gelir farki telafisi', why:'Dusuk su tuketimiyle katma deger arar; tek urune bagimliligi azaltir.', social:'Baharat pazarina giris ve kucuk parsellerde yuksek TL/m3 etkisi.'},
    {title:'Arpa/cavdar + fig yem deseni', rate:'%40 tohum + dusuk su primi', why:'Kurak yila dayanikli, yem ihtiyacini destekleyen ve topragi orten desen.', social:'Hayvancilik maliyetini ve erozyon riskini azaltir.'},
    {title:'Elma/kiraz bahcesinde damla-sensor modernizasyonu', rate:'%50 sulama yatirimi + kalite primi', why:'Nigde meyvecilikte guclu; ana urunu sokmeden su verimliligi ve ihracat kalitesi artirilir.', social:'Paketleme, depolama ve istihdam zinciri guclenir.'},
    {title:'Patateste sozlesmeli + damla + dortlu munavebe', rate:'%30-40 verimlilik primi', why:'Patates stratejik ama su baskisi yuksek; tesvik yalnizca verimli sulama ve munavebe kosuluyla dogru olur.', social:'Isleme sanayi, alim garantisi ve su adaleti birlikte korunur.'}
  ];

  const MOJI = [
    ['Ç','Ç'],['ç','ç'],['Ö','Ö'],['ö','ö'],['Ü','Ü'],['ü','ü'],
    ['İ','İ'],['ı','ı'],['Ş','Ş'],['Ş','Ş'],['ş','ş'],['Ğ','Ğ'],['Ğ','Ğ'],['ğ','ğ'],
    ['-','-'],['-','-'],['•','•'],['’',"'"],['‘',"'"],['“','"'],['”','"'],['…','...'],
    ['°','°'],['²','²'],['³','³'],['±','±'],['·','·'],['','']
  ];
  const POLISH = [
    ['Nigde','Niğde'],['ciftci','çiftçi'],['Ciftci','Çiftçi'],['yonetici','yönetici'],['Yonetici','Yönetici'],
    ['iletisim','iletişim'],['Iletisim','İletişim'],['onayli','onaylı'],['Onayli','Onaylı'],['guncel','güncel'],
    ['oner','öner'],['urun','ürün'],['Urun','Ürün'],['kar','kâr'],['Tesvik','Teşvik'],['Sec','Seç'],['Mesaj gonder','Mesaj gönder'],
    ['Secili oneriyi talep et','Seçili öneriyi talep et'],['Yanit gonder','Yanıt gönder'],['Iptal et','İptal et']
  ];
  const MOJIBAKE_RE_V142 = /[\u00c2-\u00c5\u00e2\u20ac\u0152\u0153\u0160\u0161\u0178\u017d\u017e\ufffd]/;
  const CP1252_BYTES_V142 = {
    0x20ac:0x80,0x201a:0x82,0x0192:0x83,0x201e:0x84,0x2026:0x85,0x2020:0x86,0x2021:0x87,0x02c6:0x88,
    0x2030:0x89,0x0160:0x8a,0x2039:0x8b,0x0152:0x8c,0x017d:0x8e,0x2018:0x91,0x2019:0x92,0x201c:0x93,
    0x201d:0x94,0x2022:0x95,0x2013:0x96,0x2014:0x97,0x02dc:0x98,0x2122:0x99,0x0161:0x9a,0x203a:0x9b,
    0x0153:0x9c,0x017e:0x9e,0x0178:0x9f
  };
  const utf8DecoderV142 = typeof TextDecoder !== 'undefined' ? new TextDecoder('utf-8', {fatal:false}) : null;
  function mojibakeScoreV142(text){
    return ((String(text).match(/[\u00c2-\u00c5\u00e2\u20ac\u0152\u0153\u0160\u0161\u0178\u017d\u017e]/g) || []).length * 3)
      + ((String(text).match(/[\u0080-\u009f\ufffd]/g) || []).length * 5);
  }
  function legacyBytesV142(text){
    const bytes = [];
    for(const ch of String(text)){
      const code = ch.codePointAt(0);
      if(code <= 0xff) bytes.push(code);
      else if(CP1252_BYTES_V142[code] != null) bytes.push(CP1252_BYTES_V142[code]);
      else return null;
    }
    return new Uint8Array(bytes);
  }
  function decodeMojibakeV142(value){
    if(!utf8DecoderV142) return String(value ?? '');
    let out = String(value ?? '');
    for(let i=0; i<2; i += 1){
      if(!MOJIBAKE_RE_V142.test(out)) break;
      const before = mojibakeScoreV142(out);
      const bytes = legacyBytesV142(out);
      if(!bytes) break;
      const decoded = utf8DecoderV142.decode(bytes);
      if(decoded && mojibakeScoreV142(decoded) + 1 < before) out = decoded;
      else break;
    }
    return out;
  }
  function repairMojibakeFragmentsV142(value){
    let out = String(value ?? '');
    [
      [/\u00c3[\u0087\u2021]/g,'Ç'],[/\u00c3\u00a7/g,'ç'],[/\u00c3[\u0096\u2013]/g,'Ö'],[/\u00c3\u00b6/g,'ö'],
      [/\u00c3[\u009c\u0153]/g,'Ü'],[/\u00c3\u00bc/g,'ü'],[/\u00c4\u00b0/g,'İ'],[/\u00c4\u00b1/g,'ı'],
      [/\u00c4[\u009e\u017d]/g,'Ğ'],[/\u00c4[\u009f\u0178]/g,'ğ'],[/\u00c5[\u009e\u017d\u017e]/g,'Ş'],
      [/\u00c5[\u009f\u0178]/g,'ş'],[/\u00c2\u00b0/g,'°'],[/\u00c2\u00b2/g,'²'],[/\u00c2\u00b3/g,'³'],
      [/\u00c2\u00b1/g,'±'],[/\u00c2\u00b7/g,'·'],[/\u00c2/g,'']
    ].forEach(([bad, good]) => { out = out.replace(bad, good); });
    return out;
  }
  function fixText(value){
    let out = repairMojibakeFragmentsV142(decodeMojibakeV142(value));
    for(const [bad, good] of MOJI) out = out.split(bad).join(good);
    out = repairMojibakeFragmentsV142(decodeMojibakeV142(out));
    for(const [bad, good] of POLISH){
      if(bad === 'kar') continue;
      out = out.split(bad).join(good);
    }
    [
      [/\bCiftci\b/g,'Çiftçi'],[/\bciftci\b/g,'çiftçi'],[/\bYonetici\b/g,'Yönetici'],[/\byonetici\b/g,'yönetici'],
      [/\bIletisim\b/g,'İletişim'],[/\biletisim\b/g,'iletişim'],[/\bgecmisi\b/g,'geçmişi'],[/\bmesaji\b/g,'mesajı'],
      [/\bkartindaki\b/g,'kartındaki'],[/\bSec\b/g,'Seç'],[/\bsecili\b/g,'seçili'],[/\boneriyi\b/g,'öneriyi'],
      [/\boneri\b/g,'öneri'],[/\bHazir\b/g,'Hazır'],[/\bhazirlar\b/g,'hazırlar'],[/\bhazir\b/g,'hazır'],[/\bgonder\b/g,'gönder'],
      [/\bGuncel\b/g,'Güncel'],[/\bguncel\b/g,'güncel']
    ].forEach(([bad, good]) => { out = out.replace(bad, good); });
    out = out.replace(/\bkârar\b/gi, 'karar').replace(/\bnet kar\b/gi, 'net kâr');
    return out;
  }
  function repairVisibleText(root=document.body){
    try{
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(node){
          const parent = node.parentElement;
          if(!parent || ['SCRIPT','STYLE','TEXTAREA','INPUT'].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
          if(MOJIBAKE_RE_V142.test(node.nodeValue || '')) return NodeFilter.FILTER_ACCEPT;
          if(/yonetici|iletisim|gecmis|mesaji|kartindaki|Sec\b|hazir|oneri|gonder/i.test(node.nodeValue || '')) return NodeFilter.FILTER_ACCEPT;
          return /[\u00c3\u00c4\u00c5\u00e2]|Nigde|ciftci|onayli|guncel|oner|Mesaj gonder|Secili/i.test(node.nodeValue || '') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        }
      });
      const nodes = [];
      while(walker.nextNode()) nodes.push(walker.currentNode);
      nodes.slice(0,3000).forEach(node => { node.nodeValue = fixText(node.nodeValue); });
      root.querySelectorAll('button,option,input,textarea,[title],[aria-label]').forEach(el => {
        if(el.tagName === 'OPTION') el.textContent = fixText(el.textContent);
        if('placeholder' in el) el.placeholder = fixText(el.placeholder || '');
        ['title','aria-label'].forEach(attr => { if(el.hasAttribute?.(attr)) el.setAttribute(attr, fixText(el.getAttribute(attr))); });
      });
    }catch(_e){}
  }

  function guideFor(crop){
    const n = norm(crop);
    return CROP_GUIDES.find(g => g.keys.some(k => n.includes(norm(k)))) || CROP_GUIDES[CROP_GUIDES.length - 1];
  }
  function cropMeta(crop){
    let meta = null;
    try{ meta = typeof cropMetaForAlternativeV101 === 'function' ? cropMetaForAlternativeV101(crop) : null; }catch(_e){}
    const catalog = STATE?.cropCatalog || {};
    const hit = meta || catalog[norm(crop)] || catalog[pretty(crop)] || null;
    return {
      waterPerDa:num(hit?.waterPerDa || hit?.water_m3_da || hit?.water || 0),
      profitPerDa:num(hit?.profitPerDa || hit?.net_kar_tl_da || hit?.profit || 0),
      yieldKgDa:num(hit?.yieldKgDa || hit?.expectedYieldKgDa || hit?.beklenen_verim_kg_da || 0),
      priceTlKg:num(hit?.priceTlKg || hit?.price_tl_kg || hit?.fiyat_tl_kg || 0),
      costTlDa:num(hit?.costTlDa || hit?.maliyet_tl_da || 0)
    };
  }
  function approvedRows(){ try{ return JSON.parse(localStorage.getItem(APPROVED_KEY) || '[]') || []; }catch(_e){ return []; } }
  function currentParcel(){ return (parcelData || []).find(p => String(p.id || p.parsel_id || '') === String(selectedParcelId || '')) || (parcelData || [])[0] || null; }
  function currentApprovedRecord(){
    const p = currentParcel();
    const user = String(STATE?.currentUser?.username || '');
    if(!p || !user || STATE?.currentUser?.role !== 'farmer') return null;
    return approvedRows().find(r => String(r.farmer_username || '') === user && String(r.parcel_id || '') === String(p.id || p.parsel_id || '')) || null;
  }
  function cropNamesFromPattern(pattern){
    const names = [];
    ['mainCrop','secondaryCrop','crop','name'].forEach(key => {
      const value = String(pattern?.[key] || '').trim();
      if(value && value !== '-' && value !== '—') names.push(value);
    });
    const raw = String(pattern?.patternName || '').replace(/%\d+\s*/g, '').replace(/\btek urun\b|\btek ürün\b/gi, '').trim();
    if(!names.length && raw){
      raw.split(/\s+\+\s+|\s+sonra\s+|\s*\/\s*/i).map(x => x.trim()).filter(Boolean).forEach(x => names.push(x));
    }
    return Array.from(new Set(names.map(pretty).filter(v => v && v !== '-' && v !== '—'))).slice(0, 2);
  }
  function currentWaterAndProfit(parcel){
    const area = num(parcel?.area_da || parcel?.area || 0);
    const rows = Array.isArray(parcel?.cropCurrent) ? parcel.cropCurrent : [];
    const waterFromRows = rows.reduce((sum, r) => sum + num(r.totalWater, num(r.area, area) * num(r.waterPerDa, 0)), 0);
    const profitFromRows = rows.reduce((sum, r) => sum + num(r.totalProfit, num(r.area, area) * num(r.profitPerDa, 0)), 0);
    return {
      area,
      water:num(parcel?.mevcut_su_m3 ?? parcel?.water_m3 ?? parcel?.water_m3_current, waterFromRows),
      profit:num(parcel?.mevcut_kar_tl ?? parcel?.profit_tl ?? parcel?.profit_tl_current, profitFromRows)
    };
  }
  function patternTotals(record, parcel){
    const pat = record?.pattern || {};
    const base = currentWaterAndProfit(parcel);
    const area = base.area || num(parcel?.area_da || 0);
    const water = num(pat.totalWater || pat.water || 0);
    const profit = num(pat.totalProfit || pat.profit || 0);
    return {
      area,
      water:water > 0 ? water : area * Math.max(0, cropMeta(cropNamesFromPattern(pat)[0] || '').waterPerDa),
      profit:profit > 0 ? profit : area * Math.max(0, cropMeta(cropNamesFromPattern(pat)[0] || '').profitPerDa),
      incentive:num(pat.incentiveTotal || 0),
      tlPerM3:num(pat.tlPerM3 || (profit / Math.max(1, water)), 0)
    };
  }
  function timelineHtml(crops){
    const merged = [];
    crops.map(guideFor).forEach(g => g.calendar.forEach(item => merged.push({crop:g.label, month:item[0], text:item[1]})));
    return merged.slice(0,10).map(item => `<div class="plan-time-item"><span>${esc(fixText(item.month))}</span><strong>${esc(fixText(item.crop))}</strong><p>${esc(fixText(item.text))}</p></div>`).join('');
  }
  function cropGuideHtml(crops){
    return crops.map(crop => {
      const g = guideFor(crop);
      return `<article class="crop-guide-card">
        <h4>${esc(fixText(g.label))}</h4>
        <div class="guide-kv"><span>Toprak</span><p>${esc(fixText(g.soil))}</p></div>
        <div class="guide-kv"><span>Sulama</span><p>${esc(fixText(g.irrigation))}</p></div>
        <div class="guide-kv"><span>Sıcaklık toplamı</span><p>${esc(fixText(g.gdd))}</p></div>
        <div class="risk-chip-row">${g.risks.map(r => `<span>${esc(fixText(r))}</span>`).join('')}</div>
      </article>`;
    }).join('');
  }
  function economyHtml(crops, totals){
    const areaEach = totals.area / Math.max(1, crops.length);
    const rows = crops.map(crop => {
      const m = cropMeta(crop);
      const yieldKgDa = m.yieldKgDa || 0;
      const basePrice = m.priceTlKg || 0;
      const costDa = m.costTlDa || Math.max(0, (yieldKgDa * basePrice) - (m.profitPerDa || totals.profit / Math.max(1, totals.area)));
      const values = [-0.10, 0, 0.10].map(delta => {
        const price = basePrice ? basePrice * (1 + delta) : 0;
        const gross = price ? yieldKgDa * price * areaEach : 0;
        const net = price ? gross - costDa * areaEach : (totals.profit / Math.max(1, crops.length)) * (1 + delta);
        return {delta, price, gross, net};
      });
      return {crop, basePrice, costDa, values};
    });
    return `<div class="approved-economy-table"><table><thead><tr><th>Ürün</th><th>Satış fiyatı</th><th>Brüt gelir</th><th>Gider</th><th>Net kâr</th></tr></thead><tbody>${rows.map(row => row.values.map(v => `<tr><td><strong>${esc(fixText(row.crop))}</strong><small>${v.delta === 0 ? 'baz fiyat' : (v.delta > 0 ? '+%10 fiyat' : '-%10 fiyat')}</small></td><td>${row.basePrice ? `${v.price.toFixed(2)} TL/kg` : 'proxy'}</td><td>${row.basePrice ? money(v.gross) : 'Veri yok'}</td><td>${row.costDa ? money(row.costDa * areaEach) : 'Proxy'}</td><td>${money(v.net)}</td></tr>`).join('')).join('')}</tbody></table></div>`;
  }
  function incentiveHtml(){
    return `<div class="incentive-grid-v142">${INCENTIVE_ROWS.map(row => `<article><strong>${esc(fixText(row.title))}</strong><span>${esc(fixText(row.rate))}</span><p>${esc(fixText(row.why))}</p><small>${esc(fixText(row.social))}</small></article>`).join('')}</div>`;
  }
  function approvedPlanHtml(record, parcel){
    const pat = record?.pattern || {};
    const crops = cropNamesFromPattern(pat);
    if(!crops.length) crops.push(pretty(parcel?.current_crop || parcel?.selected_pattern || 'Onaylı ürün'));
    const current = currentWaterAndProfit(parcel);
    const totals = patternTotals(record, parcel);
    const saved = Math.max(0, current.water - totals.water);
    const savePct = current.water > 0 ? (100 * saved / current.water) : 0;
    const extraDa = totals.water > 0 && totals.area > 0 ? saved / (totals.water / totals.area) : 0;
    const planWidth = current.water > 0 ? Math.max(4, Math.min(100, 100 * totals.water / current.water)) : 100;
    const waterGain = saved * Math.max(0, totals.tlPerM3 || totals.profit / Math.max(1, totals.water));
    const firstGuide = guideFor(crops[0]);
    return `<section class="approved-plan-clean-v142">
      <div class="approved-hero-v142">
        <div><span class="approved-eyebrow-v142">Uzman onaylı güncel plan</span><h3>${esc(fixText(pat.patternName || crops.join(' + ')))}</h3><p>${esc(fixText(pat.areaSplit || pat.note || record?.text || 'Bu plan uzman onayından sonra çiftçi uygulama sekmesine alınmıştır.'))}</p></div>
        <div class="approved-source-v142"><strong>${esc(fixText(record?.approved_by || 'Uzman'))}</strong><span>${esc((record?.approved_at || '').slice(0,10) || 'Onay tarihi yok')}</span></div>
      </div>
      <div class="approved-tabs-v103 approved-tabs-clean-v142"><span>Eski mevcut desen: ${esc(fixText(parcel?.current_crop || parcel?.selected_pattern || '-'))}</span><span class="active">Yeni onaylı plan: ${esc(fixText(crops.join(' + ')))}</span></div>
      <div class="approved-kpi-grid-v142">
        <div><span>Parsel alanı</span><strong>${num(totals.area).toFixed(1)} da</strong></div><div><span>Mevcut su</span><strong>${fmt(current.water)} m³</strong></div><div><span>Plan suyu</span><strong>${fmt(totals.water)} m³</strong></div><div><span>Su tasarrufu</span><strong>${fmt(saved)} m³</strong><small>%${savePct.toFixed(1)}</small></div><div><span>Net kâr</span><strong>${money(totals.profit)}</strong></div><div><span>TL/m³</span><strong>${num(totals.tlPerM3 || totals.profit / Math.max(1, totals.water)).toFixed(2)}</strong></div>
      </div>
      <div class="water-impact-v142"><div class="water-bars-v142"><div><span>Mevcut desen</span><b style="width:100%"></b><strong>${fmt(current.water)} m³</strong></div><div><span>Onaylı plan</span><b style="width:${planWidth}%"></b><strong>${fmt(totals.water)} m³</strong></div></div><div class="water-social-v142"><strong>Toplumsal fayda</strong><p>${saved > 0 ? `Bu tercih yaklaşık ${fmt(saved)} m³ suyu havzada bırakır; aynı su verimliliğiyle yaklaşık ${num(extraDa).toFixed(1)} da ek alanın pik dönemde nefes payı oluşur.` : 'Bu plan su tasarrufundan çok gelir/uygunluk hedefiyle onaylanmış görünüyor; sulama yöntemi yine verimli kullanılmalıdır.'}</p><small>Su tasarrufunun ekonomik karşılığı: yaklaşık ${money(waterGain)} TL/m³ verim etkisi.</small></div></div>
      <div class="approved-section-v142"><h4>Topraktan hasada uygulama takvimi</h4><div class="plan-timeline-v142">${timelineHtml(crops)}</div></div>
      <div class="approved-section-v142"><h4>Ürün yönetimi, sulama ve riskler</h4><div class="crop-guide-grid">${cropGuideHtml(crops)}</div></div>
      <div class="approved-section-v142"><h4>Kâr, gider ve satış fiyatı duyarlılığı</h4>${economyHtml(crops, totals)}</div>
      <div class="approved-section-v142"><h4>Niğde ölçeğinde teşvik edilebilir alternatifler</h4><p class="approved-note-v142">Model, Niğde'nin patates/elma gücünü korurken su kısıtı olan alanlarda baklagil, düşük su tahılı, kimyon ve damla modernizasyonunu öne çıkarır. Teşvik oranları doğrudan ödeme kararı değil, çiftçiyi ikna edecek karar destek aralığıdır.</p>${incentiveHtml()}</div>
      <div class="approved-footnote-v142">Dayanak: Niğde 2025 Tarımsal Yatırım Rehberi, Niğde İl Tarım duyuruları ve FAO CROPWAT/patates su yönetimi notları; parsel hesabı uygulamadaki su-kâr veri setinden türetilir. ${esc(fixText(firstGuide.incentive))}</div>
    </section>`;
  }

  function ensureApprovedPlanTab(open=false){
    if(STATE?.currentUser?.role !== 'farmer') return;
    const record = currentApprovedRecord();
    const parcel = currentParcel();
    const host = document.getElementById('tab-parcel') || document.querySelector('.tab-panel.active');
    if(!host || !parcel) return;
    document.querySelectorAll('#approvedPlanPanelV113,#approvedPlanPanelV111,#approvedPlanPanelV109,.approved-plan-v103,.approved-plan-v109').forEach(el => { if(el.id !== 'approvedPlanPanelV142') el.remove(); });
    document.querySelectorAll('#approvedPlanTabBtnV113,#approvedPlanTabBtnV111,#approvedPlanTabBtnV109').forEach(el => { if(el.id !== 'approvedPlanTabBtnV142') el.remove(); });
    let nav = document.getElementById('farmerApprovedNavV142');
    if(!nav){
      nav = document.createElement('div');
      nav.id = 'farmerApprovedNavV142';
      nav.className = 'farmer-approved-nav-v142';
      const own = document.createElement('button');
      own.type = 'button';
      own.className = 'tab active';
      own.textContent = 'Kendi parsel önerim';
      nav.appendChild(own);
    }else if(!nav.id){
      nav.id = 'farmerApprovedNavV142';
    }
    nav.className = 'farmer-approved-nav-v142';
    if(nav.parentElement !== host) host.insertBefore(nav, host.firstElementChild || null);
    let btn = document.getElementById('approvedPlanTabBtnV142');
    if(!btn){
      btn = document.createElement('button');
      btn.type = 'button';
      btn.id = 'approvedPlanTabBtnV142';
      btn.className = 'tab approved-plan-tab-v142';
      btn.textContent = 'Onaylı güncel plan';
      const own = Array.from(nav.querySelectorAll('button,.tab')).find(x => /Kendi parsel/i.test(x.textContent || ''));
      if(own && own.nextSibling) nav.insertBefore(btn, own.nextSibling); else nav.appendChild(btn);
    }
    btn.style.display = record ? '' : 'none';
    let panel = document.getElementById('approvedPlanPanelV142');
    if(!panel){
      panel = document.createElement('section');
      panel.id = 'approvedPlanPanelV142';
      panel.className = 'approved-plan-panel-v142 hidden';
      nav.insertAdjacentElement('afterend', panel);
    }
    if(!record){ panel.classList.add('hidden'); panel.innerHTML = ''; return; }
    if(open) localStorage.setItem(PLAN_OPEN_KEY, '1');
    const shouldOpen = open || localStorage.getItem(PLAN_OPEN_KEY) === '1';
    panel.classList.toggle('hidden', !shouldOpen);
    panel.innerHTML = approvedPlanHtml(record, parcel);
    btn.onclick = () => {
      nav.querySelectorAll('button,.tab').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      localStorage.setItem(PLAN_OPEN_KEY, '1');
      panel.classList.remove('hidden');
      try{ panel.scrollIntoView({behavior:'smooth', block:'start'}); }catch(_e){}
    };
  }

  function ensureBellIcon(){
    const btn = document.getElementById('notificationBellBtn');
    if(!btn) return;
    btn.setAttribute('aria-label', 'Bildirimler');
    btn.setAttribute('title', 'Bildirimler');
    let icon = btn.querySelector('.header-bell-icon');
    if(!icon){
      icon = document.createElement('span');
      icon.className = 'header-bell-icon';
      icon.setAttribute('aria-hidden', 'true');
      btn.insertBefore(icon, btn.firstChild);
    }
    icon.className = 'header-bell-icon bell-icon-clean-v142';
    icon.innerHTML = '<svg viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path><path d="M10 21h4"></path></svg>';
    if(STATE?.currentUser) btn.classList.remove('hidden');
  }

  function ensureDrawingInboxHost(){
    if(STATE?.currentUser?.role !== 'institution') return;
    const panel = document.getElementById('tab-drawing');
    const shell = panel?.querySelector('.drawing-tab-shell') || panel;
    if(!shell) return;
    let host = document.getElementById('drawingInboxBottomCleanV142') || document.getElementById('drawingInboxBottomV118');
    if(!host){
      host = document.createElement('section');
      host.id = 'drawingInboxBottomCleanV142';
      host.className = 'drawing-inbox-bottom-v142';
      shell.appendChild(host);
    }
    host.classList.add('drawing-inbox-bottom-v142');
    let inbox = document.getElementById('institutionRequestInbox');
    if(!inbox){
      inbox = document.createElement('section');
      inbox.id = 'institutionRequestInbox';
      inbox.className = 'card institution-request-inbox-v142';
    }
    inbox.classList.add('card','institution-request-inbox-v142');
    if(inbox.parentElement !== host) host.appendChild(inbox);
    if(!inbox.innerHTML.trim()){
      inbox.innerHTML = '<div class="notify-head"><strong>Kurum / uzman gelen mesajları</strong><span class="pill-soft">Hazır</span></div><div class="small muted">Çiftçi mesajları ve alternatif onay talepleri burada sabitlenir.</div>';
    }
  }
  function forceDrawingTabV142(){
    if(STATE?.currentUser?.role !== 'institution') return false;
    const panel = document.getElementById('tab-drawing');
    const btn = document.querySelector('.tab[data-tab="drawing"],button[data-tab="drawing"]');
    if(!panel || !btn) return false;
    document.querySelectorAll('.tab[data-tab]').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-panel[id^="tab-"]').forEach(el => el.classList.remove('active'));
    panel.classList.add('active');
    return true;
  }
  function ensureFarmerMessageDock(){
    if(STATE?.currentUser?.role !== 'farmer') return;
    const card = document.getElementById('farmerDecisionCard') || document.getElementById('tab-parcel');
    if(!card) return;
    let root = document.getElementById('farmerUserRequestThreadV100') || document.getElementById('userRequestThread');
    if(!root){
      root = document.createElement('div');
      root.id = 'farmerUserRequestThreadV100';
      root.className = 'farmer-message-card-v100 farmer-message-stable-v142';
      card.appendChild(root);
    }
    root.id = 'farmerUserRequestThreadV100';
    root.classList.add('farmer-message-stable-v142');
    if(root.parentElement !== card && card.contains(root) === false) card.appendChild(root);
    if(!root.innerHTML.trim()){
      root.innerHTML = '<div class="request-thread-head"><strong>Uzman / yönetici iletişim</strong><span class="pill-soft">0 mesaj</span></div><div class="small muted">Seçili öneriyi veya sorunuzu uzmana buradan iletebilirsiniz.</div><textarea class="text-input" id="farmerMessageInputV100" placeholder="Örn. Bu öneriyi uygulamak istiyorum, uzman onayı rica ederim."></textarea><div class="farmer-message-actions-v100"><button class="btn-secondary" id="farmerSendMessageV100" type="button">Mesaj gönder</button><button class="btn-secondary" id="farmerRequestSelectedV100" type="button">Seçili öneriyi talep et</button></div>';
    }
  }
  function routeBellClick(){
    ensureBellIcon();
    const role = STATE?.currentUser?.role || '';
    if(role === 'institution'){
      try{ if(typeof switchTabByKey === 'function') switchTabByKey('drawing'); }catch(_e){}
      forceDrawingTabV142();
      try{ if(typeof renderInstitutionRequestInbox === 'function') renderInstitutionRequestInbox(window.__institutionFocusThreadV111 || ''); }catch(_e){}
      forceDrawingTabV142();
      ensureDrawingInboxHost();
      const target = document.getElementById('institutionRequestInbox');
      if(target) setTimeout(() => { try{ target.scrollIntoView({behavior:'smooth', block:'start'}); }catch(_e){} }, 80);
    }else if(role === 'farmer'){
      ensureFarmerMessageDock();
      const target = document.getElementById('approvedPlanPanelV142') || document.getElementById('farmerUserRequestThreadV100');
      if(target) setTimeout(() => { try{ target.scrollIntoView({behavior:'smooth', block:'start'}); }catch(_e){} }, 80);
    }
  }
  let repairTimerV142 = 0;
  function queueTextRepairV142(){
    clearTimeout(repairTimerV142);
    repairTimerV142 = setTimeout(() => repairVisibleText(), 90);
  }
  function finalPass(openApproved=false){
    ensureBellIcon();
    ensureDrawingInboxHost();
    ensureFarmerMessageDock();
    ensureApprovedPlanTab(openApproved);
    repairVisibleText();
  }
  function schedule(openApproved=false){
    [0,120,420,1000,2200,4200,7000,12000].forEach(ms => setTimeout(() => finalPass(openApproved), ms));
  }
  if(typeof refreshUI === 'function' && !refreshUI.__v142CleanWrapped){
    const prev = refreshUI;
    refreshUI = function(){
      const res = prev.apply(this, arguments);
      schedule(false);
      return res;
    };
    refreshUI.__v142CleanWrapped = true;
  }
  try{
    if(typeof openNotificationTarget === 'function' && !openNotificationTarget.__v142CleanWrapped){
      const prevOpenNotificationTargetV142 = openNotificationTarget;
      openNotificationTarget = function(){
        const res = prevOpenNotificationTargetV142.apply(this, arguments);
        if(STATE?.currentUser?.role === 'institution'){
          [0,80,220,700,1500,2800].forEach(ms => setTimeout(() => {
            forceDrawingTabV142();
            ensureDrawingInboxHost();
            repairVisibleText();
          }, ms));
        }
        return res;
      };
      openNotificationTarget.__v142CleanWrapped = true;
    }
  }catch(_e){}
  window.__forceDrawingTabV142 = forceDrawingTabV142;
  try{
    if(typeof renderInstitutionRequestInbox === 'function' && !renderInstitutionRequestInbox.__v142CleanWrapped){
      const prev = renderInstitutionRequestInbox;
      renderInstitutionRequestInbox = function(){
        const res = prev.apply(this, arguments);
        schedule(false);
        return res;
      };
      renderInstitutionRequestInbox.__v142CleanWrapped = true;
    }
  }catch(_e){}
  document.addEventListener('click', ev => {
    if(ev.target?.closest?.('#notificationBellBtn')){
      setTimeout(routeBellClick, 40);
      schedule(false);
    }
    if(ev.target?.closest?.('#instRequestApproveV111,#instRequestApproveV109,#instRequestApproveV108,#instRequestApproveV102')){
      schedule(true);
    }
    if(ev.target?.closest?.('[data-select-pattern-v102],#farmerRunDecisionCleanV118,#farmerRunDecisionV102,#runOptBtn,.tab,.auth-demo-btn,.auth-submit,#switchUserBtn')){
      schedule(false);
    }
  }, true);
  document.addEventListener('change', ev => {
    const id = ev.target?.id || '';
    if(/farmerObjectiveSelect|farmerSeasonSourceSelect|farmerAlgoSelect|parcelSelect/.test(id)) schedule(false);
  }, true);
  try{
    const observer = new MutationObserver(() => {
      if(STATE?.currentUser?.role === 'institution') ensureDrawingInboxHost();
      if(STATE?.currentUser?.role === 'farmer') ensureFarmerMessageDock();
      queueTextRepairV142();
    });
    observer.observe(document.body, {childList:true, characterData:true, subtree:true});
  }catch(_e){}
  window.addEventListener('load', () => schedule(false));
  if(document.readyState !== 'loading') schedule(false);
  else document.addEventListener('DOMContentLoaded', () => schedule(false));
})();
