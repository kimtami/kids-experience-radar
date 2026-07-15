# Parser fixtures

These files are reduced test inputs for schema compatibility, normalization, and
privacy tests. Many are materially transformed from public response shapes; some
contain invented records or placeholders. They are not live mirrors, complete API
responses, or a dataset for redistribution.

Fixture rules:

- keep only fields required by a parser contract;
- replace applicant, operator, session, account, and internal values with explicit
  synthetic markers;
- do not include cookies, tokens, authorization headers, private URLs, or unmasked
  personal information;
- use invented content for sources whose terms restrict content publication;
- do not treat inclusion in this repository as a license to reuse a source's data,
  names, images, or trademarks.

The repository MIT License covers the original test code. Third-party facts, field
names, institution names, and marks remain subject to their owners' rights and source
terms; see `../../THIRD_PARTY_NOTICES.md`.
