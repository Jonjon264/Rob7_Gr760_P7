#!/usr/bin/env python3
"""Restore only the models referenced by the migrated hospital world.

AWS assets are pinned to a git revision; Fuel versions and archive hashes are
recorded in hospital-assets.lock.json. Downloads remain outside Git.
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'sim_ws/src/x30_worlds'
MODELS = PACKAGE / 'models'
LOCK = Path(__file__).with_name('hospital-assets.lock.json')
AWS_URL = 'https://github.com/aws-robotics/aws-robomaker-hospital-world.git'
AWS_REF = '39969a9d250135835cf13b480865647d1a87b6f4'
FUEL = 'https://fuel.gazebosim.org/1.0/OpenRobotics/models'


def download(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def texture_references(directory):
    for mesh in directory.rglob('*'):
        if mesh.suffix.lower() != '.dae':
            continue
        for image in ET.parse(mesh).getroot().iter():
            if image.tag.split('}')[-1] != 'image':
                continue
            reference = image.find('{*}init_from')
            if reference is not None and reference.text:
                value = reference.text.strip()
                if not (mesh.parent / value).is_file():
                    yield mesh, value


def repair_textures(directory):
    repaired = 0
    for mesh, value in list(texture_references(directory)):
        textures = directory / 'materials/textures'
        stem = Path(value.replace('\\', '/')).stem
        candidates = [textures / f'{stem}.png', textures / f'aws_{stem}.png']
        if directory.name.startswith('aws_robomaker_residential_'):
            candidates.append(textures / f'aws_{directory.name[len("aws_robomaker_residential_"):]}.png')
        target = next((path for path in candidates if path.is_file()), None)
        if target is None:
            raise RuntimeError(f'{mesh}: missing texture {value}')
        replacement = Path(os.path.relpath(target, mesh.parent)).as_posix()
        text = mesh.read_text()
        mesh.write_text(text.replace(escape(value), escape(replacement)))
        repaired += 1
    return repaired


def sanitize(directory):
    # Match the Classic -> Harmonic adjustments used by the old importer.
    for path in directory.rglob('*.sdf'):
        tree = ET.parse(path)
        for parent in tree.getroot().iter():
            for meta in list(parent.findall('meta')):
                parent.remove(meta)
            for material in parent.findall('material'):
                for script in list(material.findall('script')):
                    material.remove(script)
        for uri in tree.getroot().iter('uri'):
            if uri.text and uri.text.startswith('file://models/'):
                uri.text = 'model://' + uri.text[len('file://models/'):]
        tree.write(path, encoding='utf-8', xml_declaration=True)
    repair_textures(directory)


def install(source, name, provenance):
    sanitize(source)
    if not (source / 'model.sdf').is_file():
        raise RuntimeError(f'{name}: archive does not contain model.sdf')
    (source / 'PROVENANCE.json').write_text(json.dumps(provenance, indent=2) + '\n')
    destination = MODELS / name
    if destination.exists():
        raise RuntimeError(f'{destination} already exists without completed provenance; inspect it before retrying')
    shutil.move(str(source), destination)
    print(f'{name}: restored', flush=True)
    return name, provenance


def fuel_model(name, locked):
    quoted = urllib.parse.quote(name)
    base = f'{FUEL}/{quoted}'
    if locked:
        provenance = dict(locked)
    else:
        meta = json.loads(download(base))
        provenance = {key: meta.get(key) for key in ('name', 'owner', 'version', 'license_name', 'license_url')}
        provenance['source'] = base
    url = f'{base}/{provenance["version"]}/{quoted}.zip'
    archive = download(url)
    digest = hashlib.sha256(archive).hexdigest()
    if provenance.get('sha256') and provenance['sha256'] != digest:
        raise RuntimeError(f'{name}: downloaded archive differs from hospital-assets.lock.json')
    provenance.update(archive=url, sha256=digest)
    with tempfile.TemporaryDirectory(prefix='hospital-fuel-') as temporary:
        folder = Path(temporary) / name
        folder.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            for member in zipped.infolist():
                if not (folder / member.filename).resolve().is_relative_to(folder.resolve()):
                    raise RuntimeError(f'{name}: unsafe archive path')
            zipped.extractall(folder)
        (folder / 'LICENSE_FUEL.json').write_text(json.dumps(provenance, indent=2) + '\n')
        return install(folder, name, provenance)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check local assets without downloading')
    args = parser.parse_args()
    world = ET.parse(PACKAGE / 'worlds/aws_hospital/world.sdf')
    names = sorted({uri.text.strip()[len('model://'):].split('/')[0]
                    for uri in world.iter('uri') if uri.text and uri.text.startswith('model://')})
    locked = json.loads(LOCK.read_text()).get('models', {}) if LOCK.exists() else {}
    restored = {}
    missing = []
    for name in names:
        marker = MODELS / name / 'PROVENANCE.json'
        if marker.is_file() and (MODELS / name / 'model.sdf').is_file():
            restored[name] = json.loads(marker.read_text())
            if not args.check and repair_textures(MODELS / name):
                restored[name]['collada_textures'] = 'resolved to packaged model textures'
                marker.write_text(json.dumps(restored[name], indent=2) + '\n')
        else:
            missing.append(name)
    if args.check:
        if missing:
            raise SystemExit(f'{len(missing)} hospital models missing. Run: python3 docker/sim/prepare_hospital.py')
        bad_textures = list(texture_references(MODELS))
        if bad_textures:
            raise SystemExit('Hospital texture paths need repair. Run: python3 docker/sim/prepare_hospital.py')
        print(f'Hospital assets ready: {len(restored)} models')
        return
    MODELS.mkdir(exist_ok=True)
    aws_names = [name for name in missing if name.startswith('aws_robomaker_')]
    if aws_names:
        with tempfile.TemporaryDirectory(prefix='hospital-aws-') as temporary:
            repo = Path(temporary) / 'source'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', AWS_URL], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'core.sparseCheckout', 'true'], check=True)
            (repo / '.git/info/sparse-checkout').write_text('/models/\n/LICENSE\n/NOTICE\n')
            subprocess.run(['git', '-C', str(repo), 'fetch', '--depth', '1', '--filter=blob:none', 'origin', AWS_REF], check=True)
            subprocess.run(['git', '-C', str(repo), 'checkout', '-q', '--detach', 'FETCH_HEAD'], check=True)
            for name in aws_names:
                source = repo / 'models' / name
                for notice in ('LICENSE', 'NOTICE'):
                    if (repo / notice).is_file():
                        shutil.copy2(repo / notice, source / notice)
                key, info = install(source, name, {'source': AWS_URL, 'revision': AWS_REF, 'license': 'MIT-0'})
                restored[key] = info
    fuel_names = [name for name in missing if name not in aws_names]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fuel_model, name, locked.get(name)): name for name in fuel_names}
        for future in concurrent.futures.as_completed(futures):
            name, info = future.result()
            restored[name] = info
    LOCK.write_text(json.dumps({'aws_revision': AWS_REF, 'models': dict(sorted(restored.items()))}, indent=2) + '\n')
    print(f'Ready: {len(restored)}/{len(names)} hospital models. Lock file: {LOCK.relative_to(ROOT)}', flush=True)


if __name__ == '__main__':
    main()
