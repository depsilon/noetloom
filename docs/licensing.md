# Licensing

**Copyright 2026 Dylan Justin Heinrich.**

**Notice updated: October 4, 2026 (2026-10-04).**

Noetloom distributes the framework and its reusable project templates under separate
licenses. The repository's root [LICENSE](../LICENSE) remains Apache-2.0. The canonical
template license is [MIT-0](../LICENSES/MIT-0.txt), an OSI-approved license that grants
use, copying, modification, distribution, sublicensing, and sale without an attribution
condition. See the [OSI license text](https://opensource.org/license/mit-0) and the
[Apache License 2.0 text](https://www.apache.org/licenses/LICENSE-2.0).

Use the license assigned to the material you copy. This is a component-specific
license split, not an option to relicense the entire framework under MIT-0.
The package metadata expression `Apache-2.0 AND MIT-0` describes those separately
licensed components. [NOTICE](../NOTICE) carries the project-specific attribution;
the standard license terms remain unchanged.

## Repository scope

| Material | License | Scope |
| --- | --- | --- |
| Framework code, lifecycle skills in `.agents/` (or plugin `skills/`), `.noetloom/project.py`, documentation, and plugin integration | Apache-2.0 | Governed by the root [LICENSE](../LICENSE); retain applicable notices. |
| Original reusable templates in `templates/`, including readable outlines, helper-profile base templates and `domains/*/SKILL.md` | MIT-0 | Governed by [LICENSES/MIT-0.txt](../LICENSES/MIT-0.txt). `templates/LICENSE` is the copy distributed with template material. |
| Maintained example applications in `examples/` | Apache-2.0 | Repository application code follows the root license. Included templates and third-party material retain their respective exceptions. This does not set the license of independently generated applications. |
| Shared logo in `assets/logo.svg` and plugin `assets/icon.svg` | Apache-2.0 | Reused from ShardLoom at the owner's request; provenance, the sizing-only modification, and copyright are in [assets/README.md](../assets/README.md) and NOTICE. |
| Third-party material | Its applicable terms | Preserve the notices and license terms that accompany that material. |

The mechanically copied `.noetloom/templates/` resources and generated compatibility
entries retain their source templates' MIT-0 license. This exception does not relicense
the helper or canonical lifecycle skills. No private skills or third-party templates
are included in the MIT-0 designation.

When redistributing Apache-2.0 components, include the license, retain applicable source
and NOTICE attribution, and identify modified files, as required by
[section 4 of Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
MIT-0 permits adapting and redistributing the designated original templates without
an attribution requirement. These summaries explain the scope; the license texts govern.

## Generated project scope

The optional helper generator places copies of the framework's Apache-2.0 license, its NOTICE, the
MIT-0 template license, and a scope explanation in `.noetloom/licenses/`. These files
describe the licenses applicable to the included framework and template material. They
do not impose a framework license or copyright on the independent application built in
the generated project. Creating an application with Noetloom does not require making that
independent application Apache-2.0 or MIT-0, or crediting Dylan Justin Heinrich as its
author. Its owner chooses its licensing policy, subject to the applicable terms of
included material. Application code, content, and third-party dependencies retain
their own applicable terms. Preserve third-party notices when redistributing material
that requires them.

The operating method and helper reference are framework documentation under Apache-2.0,
including when copied into a project. The optional readable starter outlines remain MIT-0;
using them does not require copying the framework guide or selecting an application license.
