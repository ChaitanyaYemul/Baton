"""Upload an explicit backend configuration allowlist to the linked, scoped Baton project via stdin."""
import os
import shutil
import subprocess
import secrets
import argparse
from pathlib import Path
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
values=dotenv_values(ROOT/'.env')
project=ROOT/'.vercel/project.json'
if not project.exists():raise SystemExit('Link the Baton project first.')
import json
linked=json.loads(project.read_text())
if linked['orgId']!='team_NgKr6jpZj9NVdACMjyWeqX3X' or linked.get('projectName','baton')!='baton':
    raise SystemExit('Unexpected deployment target; refusing to upload configuration.')
if not values.get('BATON_REVIEWER_PASSWORD'):
    password=secrets.token_urlsafe(30)
    with (ROOT/'.env').open('a',encoding='utf-8') as file:
        file.write('\n# Private production reviewer password; never commit or paste in chat.\nBATON_REVIEWER_PASSWORD='+password+'\n')
    values['BATON_REVIEWER_PASSWORD']=password
settings={
    'DATABASE_URL':values.get('DATABASE_URL'),
    'GROQ_API_KEY':values.get('GROQ_API_KEY'),
    'GROQ_MODEL':values.get('GROQ_MODEL','openai/gpt-oss-20b'),
    'LLM_PROVIDER':'groq','LLM_FALLBACK_PROVIDER':'offline','LLM_TIMEOUT_SECONDS':'15',
    'BATON_DEMO':'0','BATON_SECURE_COOKIE':'1',
    'BATON_REVIEWER_PASSWORD':values['BATON_REVIEWER_PASSWORD'],
}
parser=argparse.ArgumentParser()
parser.add_argument('--only',choices=list(settings))
only=parser.parse_args().only
if only:settings={only:settings[only]}
for key in ('DATABASE_URL','GROQ_API_KEY'):
    if key in settings and not settings[key]:raise SystemExit(key+' is not configured locally.')
npm=shutil.which('npm.cmd') or shutil.which('npm')
for key,value in settings.items():
    private=key in ('DATABASE_URL','GROQ_API_KEY','BATON_REVIEWER_PASSWORD')
    command=[npm,'exec','--yes','--package=vercel','--','vercel','env','add',key,'--environment','production',
             '--type','secret' if private else 'config','--yes','--force','--scope',linked['orgId'],'--project','baton']
    result=subprocess.run(command,cwd=ROOT,input=str(value)+'\n',text=True,capture_output=True)
    if result.returncode:
        raise SystemExit(key+' upload failed; no secret values printed. Check the scoped CLI session.')
    print(key+': configured as '+('Secret' if private else 'Config'))
