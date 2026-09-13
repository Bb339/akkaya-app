"""CSV/XLSX scientific tables use the same preview/confirm transaction as core data."""
from dataclasses import asdict
from copy import deepcopy
from kds.data.import_models import Issue
from kds.domain.water_budget import WaterBudget
from kds.science.validation import validate_payload
from .normalization import numeric, boolean

MAP_SECTIONS = {'unit_parameters','irrigation','calendar'}
LIST_SECTIONS = {'rotation_rules'}
SEASON_TABLES = {'s1','s2','parcels','reservoir','delivery','crop_params','monthly_climate','water_quality','soil_params','crop_suitability','irrigation_methods'}


def payload_from_records(records):
    payload = {}
    for record in records:
        section, identity = record['section'], record['record_id']
        fields = {**record['fields'], 'source':record['source']}
        if section in MAP_SECTIONS:
            payload.setdefault(section,{})[identity]=fields
        elif section=='crop_families':
            if set(record['fields'])!={'family'} or not isinstance(fields['family'],str):
                raise ValueError('crop_families records require one text family field.')
            payload.setdefault(section,{})[identity]=fields['family']
        elif section in LIST_SECTIONS:
            payload.setdefault(section,[]).append(fields)
        else:
            payload.setdefault('seasonal_resources',{}).setdefault(section.split('.',1)[1],[]).append(fields)
    validate_payload(payload)
    return payload


def validate_table(batch, document):
    records=[];issues=[];groups={};seen=set()
    kind=batch['data_type']
    def error(message,line=None):
        issues.append(asdict(Issue('ERROR','scientific_table',message,line)))
    for row in batch['rows']:
        data={field:row['values'].get(column) for field,column in batch['mapping'].items()}
        try:
            source=str(data.get('source') or '').strip()
            if not source:raise ValueError('Every record requires an explicit source.')
            if kind=='candidates':
                record={k:str(data.get(k) or '').strip() for k in ('analysis_unit_id','crop','rotation_status')}
                if not all(record.values()):raise ValueError('Candidate identity and rotation_status are required.')
                for field in ('water_requirement_m3_da','profit_per_da','yield_ton_da','suitability'):
                    record[field]=numeric(data.get(field),field,batch['options'])
                record['allowed']=boolean(data.get('allowed'),'allowed')
                if record['allowed'] is None:raise ValueError('Explicit allowed is required.')
                if data.get('risk') not in (None,''):record['risk']=numeric(data['risk'],'risk',batch['options'])
                record['source']=source
                identity=(record['analysis_unit_id'],record['crop'])
                if identity in seen:raise ValueError('Duplicate candidate identity.')
                seen.add(identity)
                if identity[0] not in {u['external_id'] for u in document['analysis_units']} or identity[1] not in {c['name'] for c in document['crops']}:
                    raise ValueError('Candidate references an unknown project unit or crop.')
                records.append(record)
            elif kind=='water_budget':
                records.append(asdict(WaterBudget(document['project']['id'],numeric(data.get('amount'),'amount',batch['options']),str(data.get('unit')),str(data.get('kind')),source=source)))
            else:
                section=str(data.get('section') or '').strip();identity=str(data.get('record_id') or '').strip();field=str(data.get('field') or '').strip()
                if section not in MAP_SECTIONS|LIST_SECTIONS|{'crop_families'}|{'seasonal_resources.'+s for s in SEASON_TABLES}:
                    raise ValueError('Unknown scientific table section: '+section)
                if not identity or not field or field=='source':raise ValueError('record_id and a non-source field are required.')
                value=data.get('value');value_type=data.get('value_type')
                if value_type=='number':value=numeric(value,field,batch['options'])
                elif value_type=='integer':
                    value=numeric(value,field,batch['options'])
                    if not float(value).is_integer():raise ValueError('Integer field contains a fractional value.')
                    value=int(value)
                elif value_type=='boolean':
                    value=boolean(value,field)
                    if value is None:raise ValueError('Boolean field is empty.')
                elif value_type=='text':
                    if value is None or not str(value).strip():raise ValueError('Text field is empty.')
                    value=str(value)
                else:raise ValueError('value_type must be text, number, integer or boolean.')
                record=groups.setdefault((section,identity),dict(section=section,record_id=identity,fields={},source=source))
                if field in record['fields']:raise ValueError('Duplicate field in scientific record.')
                if record['source']!=source:raise ValueError('A scientific record must have one consistent source.')
                record['fields'][field]=value
        except (ValueError,TypeError) as exc:error(str(exc),row['line'])
    try:
        if kind=='scientific_inputs':
            records=list(groups.values());payload_from_records(records)
        elif kind=='candidates':validate_payload({'candidates':records})
        elif len(records)!=1:raise ValueError('A water budget upload must contain exactly one record.')
    except ValueError as exc:error(str(exc))
    if not issues:issues.append(asdict(Issue('INFO','validated','Explicit values parsed; scientific readiness is evaluated after confirmation.')))
    return issues,records


def apply_records(document,batch,records):
    kind=batch['data_type']
    if kind=='water_budget':
        document['water_budget']=deepcopy(records[0])
        document['project']['annual_water_budget']=records[0]['amount']
        document['project']['water_budget_unit']=records[0]['unit']
    else:
        extra=document.setdefault('scientific_inputs',{})
        if kind=='candidates':extra['candidates']=deepcopy(records)
        else:
            payload=payload_from_records(records)
            seasonal=payload.pop('seasonal_resources',None)
            extra.update(payload)
            if seasonal is not None:extra.setdefault('seasonal_resources',{}).update(seasonal)
    document['metadata'].setdefault('scientific_imports',{})[kind]=dict(batch_id=batch['id'],file_hash=batch['file_hash'],source='public-import')
