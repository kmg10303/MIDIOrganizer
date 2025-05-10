import mido
import music21
import pretty_midi
from .midi_analyzer import MidiAnalyzer
from io import BytesIO

class MidiAdjuster:
    def __init__(self, analyzer):
        self.file = analyzer.uploaded_file
        self.analyzer = analyzer  # instance of MidiAnalyzer
        self.pm = analyzer.pretty_file  # PrettyMIDI object

    def _export(self, name):
        new_name = f"{name}.mid"

        output = BytesIO()
        self.pm.write(output)
        output.seek(0)
        output.name = new_name  # ✅ critical
        return output
        

    def file_name_bpm(self):
        analyzer = self.analyzer
        bpm = analyzer.detect_bpm()
        # Get clean name
        original_name = self.analyzer.name  # Make sure this exists

        # Create custom name with BPM
        name = f"{original_name}_{int(bpm)}"
        return self._export(name)

    def file_name_key(self):
        analyzer = self.analyzer
        key = analyzer.detect_key()

        original_name = self.analyzer.name
    
        name = f"{original_name}_{key}"

        return self._export(name)

    def beat_match(self, target_bpm, target_file_name):
        original_bpm = self.analyzer.detect_bpm()

        if original_bpm > 144:
            original_bpm /= 2
        if target_bpm > 144:
            target_bpm /= 2
        

        if abs(original_bpm - target_bpm) > 22 and abs(original_bpm - target_bpm) <= 42:
            target_bpm = (target_bpm + original_bpm) / 2
        elif abs(original_bpm - target_bpm) > 42:
            return self._export(f"{self.analyzer.name}_skip_{original_bpm}")

        # Calculate scaling factor
        scaling_factor = original_bpm / target_bpm

        # Adjust timing of file2
        for instrument in self.pm.instruments:
            for note in instrument.notes:
                note.start *= scaling_factor
                note.end *= scaling_factor
            for bend in instrument.pitch_bends:
                bend.time *= scaling_factor
            for cc in instrument.control_changes:
                cc.time *= scaling_factor

        for ts in self.pm.time_signature_changes:
            ts.time *= scaling_factor

        for ks in self.pm.key_signature_changes:
            ks.time *= scaling_factor

        original_name = self.analyzer.name

        name = f"{original_name}_{int(original_bpm)}bpm2{target_file_name}_{target_bpm}bpm"

        return self._export(name)
    



        