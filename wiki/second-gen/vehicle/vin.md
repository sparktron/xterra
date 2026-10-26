# VIN decoding

[Reference home](index.md)

What NHTSA's VIN decoder (vPIC) reads from Xterra-pattern VINs [S30][S31][S32]. These are pattern decodes of sample VINs, not records of real vehicles.

| Position | Meaning | Values seen | Source |
|---|---|---|---|
| 1-3 | Manufacturer identifier | 5N1: Nissan North America, Inc. | [S30] |
| 8 | Drive type | U: 4x2; W: 4WD | [S30][S32] |
| 9 | Check digit | computed from the other characters; vPIC flags a mismatch | [S30] |
| 10 | Model year | 5 = 2005, 6 = 2006, 7 = 2007, 8 = 2008, 9 = 2009, A = 2010, B = 2011, C = 2012, D = 2013, E = 2014, F = 2015 | [S30] |
| 11 | Assembly plant | C: Smyrna, Tennessee; N: Canton, Mississippi | [S30][S31] |
| 12-17 | Serial number | - | [S30] |

The model-year table above was checked by decoding one sample VIN per letter on vPIC [S30]. vPIC also decodes the body as a 4-door SUV/MPV, GVWR class 1D (5,001-6,000 lb), 4.0 L gasoline [S30].

Positions 4-7 vary by year and model line, and no source used here explains them [Unverified]. Decode a real VIN at vpic.nhtsa.dot.gov.

## Where the numbers are on the vehicle

- The VIN plate and the engine serial number locations are shown in the owner's manual's 'Vehicle identification' illustrations [S115].
- The F.M.V.S.S./C.M.V.S.S. certification label, with GVWR, axle ratings, month and year of manufacture and the VIN, is on the center pillar between the driver's-side front and rear doors [S115].
- The emission control information label and the air conditioner specification label are under the hood [S115].

## Sources

All web sources accessed 2026-10-07. Numbers are the source's own; `[Unverified]` marks anything no listed source states.

- [S30] NHTSA vPIC VIN decoder API (pattern decodes of sample Xterra VINs). https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/5N1AN08W05C600000?format=json
- [S31] NHTSA vPIC VIN decoder API (sample decode, 2015 pattern, Canton plant letter). https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/5N1AN0NW0FN600000?format=json
- [S32] NHTSA vPIC VIN decoder API (sample decode, 2005 4x2 pattern). https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/5N1AN08U05C600000?format=json
- [S115] Nissan, 2015 Xterra Owner's Manual (Technical and consumer information; Maintenance and do-it-yourself). https://owners.nissanusa.com/content/techpub/ManualsAndGuides/Xterra/2015/2015-Xterra-owner-manual.pdf
