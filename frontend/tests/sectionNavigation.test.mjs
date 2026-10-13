import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

// Use the project's compiler so tests also work on supported Node 20 runtimes.
const source = await readFile(new URL('../src/sectionNavigation.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022,
} }).outputText
const { sectionAtFocus, sectionScrollTop, scrolledToBottom } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('no navigation entry exists for an empty project', () => {
  assert.equal(sectionAtFocus([], 180, false), -1)
})
test('the first section is active before its title reaches the reading line', () => {
  assert.equal(sectionAtFocus([260, 620, 940], 180, false), 0)
})
test('the latest section above the reading line stays active through long content', () => {
  assert.equal(sectionAtFocus([-600, 120, 480], 180, false), 1)
  assert.equal(sectionAtFocus([-1600, -900, 280], 180, false), 1)
  assert.equal(sectionAtFocus([-1900, -1200, 100], 180, false), 2)
})
test('the final short section is reachable at the end of the page', () => {
  assert.equal(sectionAtFocus([-600, 100, 340], 180, true), 2)
})

test('section travel uses the scrolling pane offset, not the window scroll', () => {
  assert.equal(sectionScrollTop(250, 340, 101), 469)
  assert.equal(sectionScrollTop(0, 110, 101), 0)
})
test('focus follows headings relative to a scroller below the fixed header', () => {
  const viewportTop = 101
  assert.equal(sectionAtFocus([20, 260, 540].map(top => top - viewportTop), 180, false), 1)
})
test('bottom detection uses the pane height and does not select the last section on an unscrolled short page', () => {
  assert.equal(scrolledToBottom(1200, 700, 1900), true)
  assert.equal(scrolledToBottom(500, 700, 1900), false)
  assert.equal(scrolledToBottom(0, 700, 500), false)
})
