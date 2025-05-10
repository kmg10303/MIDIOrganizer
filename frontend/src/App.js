import React, { useState, useRef } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [outputFormat, setOutputFormat] = useState('filesystem');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const folderInputRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const files = folderInputRef.current?.files;
    
    if (!files || files.length === 0) {
      setError('Please select a folder containing song folders');
      return;
    }

    setIsProcessing(true);
    setError('');
    setDownloadUrl('');

    try {
      const formData = new FormData();
      formData.append('output_format', outputFormat);

      Array.from(files).forEach(file => {
        formData.append('files', file, file.webkitRelativePath);
      });

      const response = await axios.post(
        'http://localhost:8000/api/generate-midi-mashups/', 
        formData, 
        {
          responseType: outputFormat === 'csv' ? 'blob' : 'arraybuffer',
        }
      );
      
      const blob = new Blob([response.data], {
        type: outputFormat === 'csv' ? 'text/csv' : 'application/zip'
      });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = outputFormat === 'csv' ? 'mashups.csv' : 'mashups.zip';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      

    } catch (err) {
      setError(err.response?.data?.error || 'Processing failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Midi Organizer</h1>
        <p>Folder structure should contain subfolders for each midi, with vocal, instrumental, and full versions</p>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Select Root Folder:</label>
            <input
              type="file"
              ref={folderInputRef}
              onChange={() => setError('')}
              webkitdirectory="true"
              multiple
            />
          </div>
          
          <div className="form-group">
            <label>Output Format:</label>
            <select 
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
            >
              <option value="filesystem">Structured Filesystem</option>
              <option value="csv">CSV File</option>
            </select>
          </div>
          
          <button type="submit" disabled={isProcessing}>
            {isProcessing ? 'Processing...' : 'Generate Mashups'}
          </button>
        </form>
        
        {error && <div className="error">{error}</div>}
        
        {downloadUrl && (
          <div className="download-section">
            <a
              href={downloadUrl}
              download={`mashups.${outputFormat === 'csv' ? 'csv' : 'zip'}`}
              className="download-button"
            >
              Download {outputFormat === 'csv' ? 'CSV' : 'ZIP'}
            </a>
          </div>
        )}
      </header>
    </div>
  );
}

export default App;