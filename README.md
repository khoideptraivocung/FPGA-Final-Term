# Topic22 starter — Python reference + ROM

## Requirements
- Python 3.10+
- NumPy

Install:
```bash
python -m pip install numpy
```

Run reference:
```bash
python python/reference_model.py
```

Regenerate ROM:
```bash
python python/generate_data.py
```

## Files
- `SPECIFICATION_v1.0.md`: arithmetic and interface contract
- `rom/test_vectors.mem`: 1024 signed 12-bit words, one 3-digit hex word per line
- `python/reference_model.py`: fixed-point MA and FIR reference
- `python/generate_data.py`: deterministic test-data generator
- `results/python_reference.csv`: expected outputs

The ROM samples are synthetic test data, not real sensor measurements.
