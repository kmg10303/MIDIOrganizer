import os
import csv
import zipfile
import tempfile
import re
from collections import defaultdict
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view
import logging
from io import BytesIO
from .services.midi_analyzer import MidiAnalyzer
from .services.midi_adjuster import MidiAdjuster
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import parser_classes

logger = logging.getLogger(__name__)

def analyze_midi_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            analyzer = MidiAnalyzer(f)
            bpm = analyzer.detect_bpm()
            key = analyzer.detect_key()
            print(f"Key: {key}, BPM: {bpm}")
            return {'bpm': bpm, 'key': key}
    except Exception as e:
        logger.warning(f"Analysis failed for {file_path}: {e}")
        return None

def clean_name(name):
    name = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r'[^\w\s\-]', '', name).strip().replace(' ', '_')

def beatmatch_midi(input_path, original_bpm, target_bpm, output_path):
    try:
        with open(input_path, 'rb') as f:
            analyzer = MidiAnalyzer(f)
            adjuster = MidiAdjuster(analyzer)
            
            if abs(original_bpm - target_bpm) > 42:
                print(f"Skipping beatmatching for {input_path} due to BPM difference")
                return None
            
            adjusted = adjuster.beat_match(target_bpm, "adjusted")
            if adjusted:
                with open(output_path, 'wb') as out_file:
                    out_file.write(adjusted.getvalue())
                print(f"Beatmatched {input_path} from {original_bpm} to {target_bpm} BPM")
                return output_path
            return None
    except Exception as e:
        logger.warning(f"Beatmatching failed: {e}")
        return None

def beatmatch_songs(songs):
    if not songs:
        return []
    bpms = [s['bpm'] for s in songs]
    target_bpm = max(set(bpms), key=bpms.count)
    for s in songs:
        s['target_bpm'] = target_bpm
    return songs

def create_zip_response(files):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for f in files:
            if os.path.exists(f['source_path']):
                zipf.write(f['source_path'], f['zip_path'])
            else:
                logger.warning(f"File missing during zip: {f['source_path']}")
    resp = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    resp['Content-Disposition'] = 'attachment; filename="midi_mashups.zip"'
    return resp

@csrf_exempt
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def generate_midi_mashups(request):
    logger.info("generate_midi_mashups called")
    try:
        files = request.FILES.getlist('files')
        if not files:
            return JsonResponse({'error': 'No files uploaded'}, status=400)

        output_format = request.POST.get('output_format', 'filesystem')

        temp_dir = tempfile.mkdtemp()
        for f in files:
            save_path = os.path.join(temp_dir, f.name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb+') as dest:
                for chunk in f.chunks():
                    dest.write(chunk)

        # Process all MIDI files as complete tracks
        songs = []
        for root, _, fs in os.walk(temp_dir):
            for f in fs:
                if f.lower().endswith(('.mid', '.midi')):
                    file_path = os.path.join(root, f)
                    analysis = analyze_midi_file(file_path)
                    if analysis:
                        raw_name = clean_name(f)
                        songs.append({
                            'name': raw_name,
                            'file_path': file_path,
                            'bpm': analysis['bpm'],
                            'key': analysis['key'],
                            'original_bpm': analysis['bpm'],
                            'artist': raw_name.split('-')[0] if '-' in raw_name else 'Unknown'
                        })

        if not songs:
            return JsonResponse({'error': 'No valid MIDI files found'}, status=400)

        # Define consistent fieldnames for CSV
        fieldnames = [
            'Song A Title', 'Song A Artist', 'Song A Key', 'Song A Tempo', 'Song A Path',
            'Song B Title', 'Song B Artist', 'Song B Key', 'Song B Tempo', 'Song B Path'
        ]

        key_groups = defaultdict(list)
        for song in songs:
            key_groups[song['key']].append(song)

        beatmatched_groups = {k: beatmatch_songs(g) for k, g in key_groups.items()}

        csv_data = []
        files_to_zip = []

        for key, group in beatmatched_groups.items():
            for i, s1 in enumerate(group):
                for j, s2 in enumerate(group):
                    if len(group) == 1:
                        # Single song in this key group
                        song = group[0]
                        solo_folder = f"{song['key']}/{song['name']}"
                        files_to_zip.append({
                            'source_path': song['file_path'],
                            'zip_path': f"{solo_folder}/{song['name']}^{song['artist']}^{song['key']}^{round(song['bpm'])}^Song A.mp3"
                        })
                        csv_data.append({
                            'Song A Title': song['name'],
                            'Song A Artist': song['artist'],
                            'Song A Key': song['key'],
                            'Song A Tempo': round(song['bpm'], 1),
                            'Song A Path': f"{solo_folder}/{song['name']}^{song['artist']}^{song['key']}^{round(song['bpm'])}^Song A.mp3",
                            'Song B Title': '',
                            'Song B Artist': '',
                            'Song B Key': '',
                            'Song B Tempo': '',
                            'Song B Path': ''
                        })
                    else:
                        if i == j:
                            continue
                            
                        # Create mashup pair
                        mashup_folder = f"{s1['key']}/{s1['name']} + {s2['name']}"
                        new_bpm = s1['original_bpm']
                        
                        # Add first song
                        files_to_zip.append({
                            'source_path': s1['file_path'],
                            'zip_path': f"{mashup_folder}/{s1['name']}^{s1['artist']}^{s1['key']}^{round(s1['bpm'],1)}^Song A.mp3"
                        })
                        
                        # Handle second song with possible beatmatching
                        if abs(s2['bpm'] - s1['original_bpm']) <= 22:
                            adjusted_path = os.path.join(temp_dir, f"adjusted_{s2['name']}.mid")
                            adjusted = beatmatch_midi(
                                s2['file_path'],
                                original_bpm=s2['bpm'],
                                target_bpm=s1['original_bpm'],
                                output_path=adjusted_path
                            )
                        elif abs(s2['bpm'] - s1['original_bpm']) > 42:
                            print(f"Skipping beatmatching for {s2['name']} due to BPM difference")
                            adjusted = None
                        else:
                            new_bpm = (s1['original_bpm'] + s2['bpm']) / 2
                            print(f"Average BPM for {s1['name']} and {s2['name']}: {new_bpm}")
                            adjusted_path = os.path.join(temp_dir, f"adjusted_{s2['name']}.mid")
                            adjusted = beatmatch_midi(
                                s2['file_path'],
                                original_bpm=s2['bpm'],
                                target_bpm=new_bpm,
                                output_path=adjusted_path
                            )
                        
                        if adjusted:
                            files_to_zip.append({
                                'source_path': adjusted,
                                'zip_path': f"{mashup_folder}/{s2['name']}^{s2['artist']}^{s2['key']}^{round(new_bpm,1)}^Song B.mp3"
                            })
                        else:
                            files_to_zip.append({
                                'source_path': s2['file_path'],
                                'zip_path': f"{mashup_folder}/{s2['name']}^{s2['artist']}^{s2['key']}^{round(new_bpm,1)}^Song B.mp3"
                            })
                            
                        csv_data.append({
                            'Song A Title': s1['name'],
                            'Song A Artist': s1['artist'],
                            'Song A Key': s1['key'],
                            'Song A Tempo': round(new_bpm, 1),
                            'Song B Title': s2['name'],
                            'Song B Artist': s2['artist'],
                            'Song B Key': s2['key'],
                            'Song B Tempo': round(new_bpm, 1),
                            'Song A Path': f"{mashup_folder}/{s1['name']}^{s1['artist']}^{s1['key']}^{round(s1['bpm'],1)}^Song A.mp3",
                            'Song B Path': f"{mashup_folder}/{s2['name']}^{s2['artist']}^{s2['key']}^{round(new_bpm,1)}^Song B.mp3"
                        })

        # Write CSV
        csv_path = os.path.join(temp_dir, 'mu_prep_summary.csv')
        with open(csv_path, 'w', newline='') as csvfile:
            fieldnames = [
                'Song A Title', 
                'Song A Artist', 
                'Song A Key', 
                'Song A Tempo',
                'Song A Path',
                'Song B Title', 
                'Song B Artist', 
                'Song B Key', 
                'Song B Tempo',
                'Song B Path'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_data:
                # Convert absolute paths to relative if needed
                for key in row:
                    if 'path' in key and row[key]:
                        row[key] = os.path.relpath(row[key], temp_dir)
                writer.writerow(row)

        print(f"Metadata summary written to: {csv_path}")
        
        files_to_zip.append({
            'source_path': csv_path,
            'zip_path': 'mu_prep_summary.csv'
        })

        if output_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="mashups.csv"'
            
            # Ensure 'original_bpm' is included in the fieldnames
            fieldnames = list(csv_data[0].keys())
            writer = csv.DictWriter(response, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_data:
                filtered_row = {k: row[k] for k in fieldnames if k in row}
                writer.writerow(filtered_row)

            return response
        else:
            return create_zip_response(files_to_zip)

    except Exception as e:
        logger.exception("Processing failed")
        return JsonResponse({'error': 'Internal server error'}, status=500)