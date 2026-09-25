import base64, json, re

def build_mpt_task(plan):
    terms=[x.strip('- \t') for x in re.split(r'[\n;]+', plan.visual_direction or '') if x.strip()]
    terms=(terms+['payment verification close-up','freelancer reviewing account','credited balance confirmation'])[:]
    return {'video_subject':plan.topic,'video_script':plan.script,'video_terms':terms,'video_aspect':'9:16','video_source':'pexels','video_concat_mode':'sequential','video_clip_duration':5,'match_materials_to_script':True,'video_count':1,'video_language':'en-US','voice_name':'en-US-JennyNeural-Female','voice_rate':1.08,'subtitle_enabled':True,'subtitle_position':'custom','custom_position':72,'font_name':'BeVietnamPro-Bold.ttf','font_size':54,'stroke_width':2.0}
def build_render_payload(plan): return build_mpt_task(plan)
def build_production_spec(plan, provider='github'):
    provider = str(provider or '').strip().lower()
    if provider == 'github':
        task=build_mpt_task(plan); raw=json.dumps(task,ensure_ascii=False).encode();
        return {'provider':'github','task_type':'video_batch','workflow':'render-short01.yml','branch':'main','content_id':plan.content_id,'hook':plan.hook,'script':plan.script,'cta':plan.cta,'title':plan.title,'description':plan.description,'artifact_name':f'remote-pay-guide-{plan.content_id}','asset_path':'final-output.mp4','asset_filename':f'{plan.content_id}.mp4','task_payload':task,'task_payload_b64':base64.b64encode(raw).decode(),'template':'short_video_template','voice':task['voice_name'],'visual_direction':plan.visual_direction}
    if provider == 'ai_gateway':
        return {'provider':'ai_gateway','task_type':'video_generation','workflow':'','branch':'main','content_id':plan.content_id,'objective':plan.topic,'prompt':plan.script,'script':plan.script,'title':plan.title,'description':plan.description,'visual_direction':plan.visual_direction,'template':'short_video_template','parameters':{'task_type':'video_generation','prompt':plan.script,'input':{'content_id':plan.content_id,'topic':plan.topic,'script':plan.script,'visual_direction':plan.visual_direction,'title':plan.title,'description':plan.description},'options':{'aspect_ratio':'9:16'}}}
    raise ValueError('unsupported production provider')
