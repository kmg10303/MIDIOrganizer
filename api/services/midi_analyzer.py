import music21
import pretty_midi
from io import BytesIO
import tempfile
from math import floor
import os

class MidiAnalyzer:
    def __init__(self, file):
        self.uploaded_file = file
        self.original_filename = file.name
        base, ext = os.path.splitext(file.name)
        self.name = base

        file.seek(0)
        midi_data = file.read()

        self.stream = BytesIO(midi_data)
        self.stream.seek(0)
        
        self.pretty_file = pretty_midi.PrettyMIDI(self.stream)

    def detect_bpm(self):
        estimate_bpm = self.pretty_file.estimate_tempo()
        return floor(estimate_bpm/2)
    
    def detect_key(self, verbose=False):
        # Write to a temporary file so music21 can parse it reliably
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=True) as temp:
            temp.write(self.stream.getbuffer())
            temp.flush()

            try:
                score = music21.converter.parse(temp.name)
                key = score.analyze("key").name
                if verbose: return key
                if key.split()[1] == "major":
                    tonic = key.split()[0].upper()
                else:
                    tonic = key.split()[0].lower()
                return tonic
            except Exception as e:
                return f"Error: {str(e)}"
    

