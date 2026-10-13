// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const { splitMulti, multiMatch, normalizeFilterValue } = require('../static/filter_utils.js');

test('splitMulti keeps slash-containing values whole', () => {
  assert.deepEqual(
    splitMulti('Corporate legal; Government / Public Sector; Litigation / Disputes Teams'),
    ['Corporate legal', 'Government / Public Sector', 'Litigation / Disputes Teams']
  );
});

test('splitMulti still splits on ; , | and newlines', () => {
  assert.deepEqual(splitMulti('A; B, C | D\nE'), ['A', 'B', 'C', 'D', 'E']);
  assert.deepEqual(splitMulti(''), []);
  assert.deepEqual(splitMulti(null), []);
});

test('segment options containing "/" match tagged tools', () => {
  const rec = 'Corporate legal; Contract Management Teams / Procurement';
  assert.equal(multiMatch(rec, ['Contract Management Teams / Procurement'], 'Primary User Segment'), true);
  assert.equal(multiMatch('Litigation / Disputes Teams', ['Litigation / Disputes Teams'], 'Primary User Segment'), true);
  assert.equal(multiMatch('Government / Public Sector', ['Government / Public Sector'], 'Primary User Segment'), true);
});

test('trailing full stop and case differences do not block a match', () => {
  assert.equal(multiMatch('Intellectual Property Teams', ['Intellectual Property Teams.'], 'Primary User Segment'), true);
  assert.equal(normalizeFilterValue('Quick win'), normalizeFilterValue('Quick Win'));
  assert.equal(normalizeFilterValue('Enterprise-Grade'), normalizeFilterValue('Enterprise-grade'));
});

test('non-matching segment is still excluded', () => {
  assert.equal(multiMatch('Corporate legal', ['Private practice'], 'Primary User Segment'), false);
});

test('Global vendors pass every region filter', () => {
  assert.equal(multiMatch('Global', ['Australia'], 'Regions Served'), true);
  assert.equal(multiMatch('Global (including Australia/ANZ)', ['Australia'], 'Regions Served'), true);
  assert.equal(multiMatch('Global (including Australia/ANZ)', ['Middle East'], 'Regions Served'), true);
});

test('region-specific vendors only pass their own regions', () => {
  assert.equal(multiMatch('North America (US & Canada); Europe (UK & EU)', ['Australia'], 'Regions Served'), false);
  assert.equal(multiMatch('Australia; United Kingdom', ['Australia'], 'Regions Served'), true);
});

test('tools with no region data stay visible under a region filter', () => {
  assert.equal(multiMatch('', ['Australia'], 'Regions Served'), true);
  assert.equal(multiMatch(null, ['Australia'], 'Regions Served'), true);
});

test('"Global" only means everywhere for the region field', () => {
  assert.equal(multiMatch('Global', ['Corporate legal'], 'Primary User Segment'), false);
});
