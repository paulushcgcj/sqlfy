import { validateMigrations } from './validateMigrations';
import type { MigrationFile } from '@/core/types';

function files(...names: string[]): MigrationFile[] {
  return names.map((filename) => ({ filename, sql: '' }));
}

describe('validateMigrations', () => {
  describe('valid sets — no issues', () => {
    it('passes a sequential V1, V2, V3 set', () => {
      const r = validateMigrations(files('V1__a.sql', 'V2__b.sql', 'V3__c.sql'));
      expect(r.hasErrors).toBe(false);
      expect(r.hasWarnings).toBe(false);
      expect(r.issues).toHaveLength(0);
    });

    it('passes dotted versioning V1.2.3', () => {
      const r = validateMigrations(
        files('V1__a.sql', 'V1.1__b.sql', 'V1.2__c.sql', 'V2__d.sql'),
      );
      expect(r.hasErrors).toBe(false);
      expect(r.hasWarnings).toBe(false);
    });

    it('accepts repeatable R__ migrations without issues', () => {
      const r = validateMigrations(files('V1__a.sql', 'R__seed.sql', 'V2__b.sql'));
      expect(r.hasErrors).toBe(false);
      expect(r.hasWarnings).toBe(false);
    });

    it('returns total count', () => {
      const r = validateMigrations(files('V1__a.sql', 'V2__b.sql'));
      expect(r.total).toBe(2);
    });

    it('returns empty result for an empty file list', () => {
      const r = validateMigrations([]);
      expect(r.issues).toHaveLength(0);
      expect(r.hasErrors).toBe(false);
    });
  });

  describe('invalid_format', () => {
    it('flags a file not matching any Flyway pattern', () => {
      const r = validateMigrations(files('my_migration.sql'));
      const issue = r.issues.find((i) => i.type === 'invalid_format');
      expect(issue).toBeDefined();
      expect(issue?.severity).toBe('warning');
      expect(issue?.filename).toBe('my_migration.sql');
    });

    it('does not flag valid V/R/U formats', () => {
      const r = validateMigrations(files('V1__a.sql', 'R__b.sql', 'U1__c.sql'));
      expect(r.issues.filter((i) => i.type === 'invalid_format')).toHaveLength(0);
    });
  });

  describe('duplicate_version', () => {
    it('flags two files with the same version number', () => {
      const r = validateMigrations(files('V1__a.sql', 'V2__b.sql', 'V1__c.sql'));
      const dupe = r.issues.find((i) => i.type === 'duplicate_version');
      expect(dupe).toBeDefined();
      expect(dupe?.severity).toBe('error');
      expect(r.hasErrors).toBe(true);
    });
  });

  describe('out_of_order', () => {
    it('flags V3 appearing before V2 by filename order', () => {
      const r = validateMigrations(files('V1__a.sql', 'V3__b.sql', 'V2__c.sql'));
      const ooo = r.issues.find((i) => i.type === 'out_of_order');
      expect(ooo).toBeDefined();
      expect(ooo?.severity).toBe('error');
    });

    it('does not flag correctly sorted files', () => {
      const r = validateMigrations(files('V1__a.sql', 'V2__b.sql', 'V3__c.sql'));
      expect(r.issues.filter((i) => i.type === 'out_of_order')).toHaveLength(0);
    });
  });

  describe('version_gap', () => {
    it('flags a gap in simple integer versions (V1, V2, V4)', () => {
      const r = validateMigrations(files('V1__a.sql', 'V2__b.sql', 'V4__c.sql'));
      const gap = r.issues.find((i) => i.type === 'version_gap');
      expect(gap).toBeDefined();
      expect(gap?.severity).toBe('warning');
      expect(gap?.message).toContain('V3');
    });

    it('does not flag gaps in dotted versions (V1, V1.1, V2 is fine)', () => {
      const r = validateMigrations(files('V1__a.sql', 'V1.1__b.sql', 'V2__c.sql'));
      expect(r.issues.filter((i) => i.type === 'version_gap')).toHaveLength(0);
    });

    it('reports multiple missing versions in one gap', () => {
      const r = validateMigrations(files('V1__a.sql', 'V5__b.sql'));
      const gap = r.issues.find((i) => i.type === 'version_gap');
      expect(gap?.message).toContain('V2');
      expect(gap?.message).toContain('V4');
    });
  });
});
