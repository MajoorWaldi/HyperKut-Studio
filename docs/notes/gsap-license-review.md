# GSAP usage review — 2026-10-28

## Source and result

Reviewed [GSAP's Standard License and FAQ](https://gsap.com/community/standard-license/), including its official FAQ, not third-party summaries. GSAP 3.15.0 remains a separately licensed dependency; it is not MIT/Apache and is not relicensed by HyperKut.

The official FAQ expressly permits AI-generated GSAP code and encourages niche visual tools that do not directly compete with Webflow's rich animation-building capabilities. Commercial usage alone is not prohibited. The restriction concerns certain competing visual animation builders, not every application that creates animation. Proprietary notices must remain intact.

## How HyperKut uses it

HyperKut directs and edits local videos. It exports MP4, not websites. The renderer creates local HTML compositions and uses GSAP timelines as a deterministic clock. The shared graphic-layer compositor draws from measured time; the Studio exposes motion directions, presets and layer JSON. It does not export a general-purpose website builder. HyperFrames and GSAP are installed separately; their runtime trees are not included in the MIT source distribution.

These facts and the FAQ support treating this as a niche video tool rather than a direct Webflow animation-builder competitor. **That is a documented interpretation, not written approval from Webflow.** No automatic paid-license requirement or confirmed violation was identified. Retain separate notices and reassess if a general visual web-animation builder is added.

For an authoritative product-specific answer, use [GSAP's official contact](https://gsap.com/community/contact). A draft is supplied below; it has not been sent. Do not claim publisher approval or remove the dependency based on an unresolved interpretation.

## Optional clarification request — draft, not sent

Subject: Standard-license clarification for HyperKut, a local open-source video studio

Hello GSAP team,

We are preparing HyperKut Studio, an MIT-licensed ComfyUI application for generating and editing local videos. It uses HyperFrames and GSAP 3.15.0 to render timed HTML overlays into MP4 files. Users choose video motion presets and can edit layer JSON. It is not a website builder and does not export websites, but it does offer visual controls for video effects.

Your FAQ describes permitted AI-generated code and niche visual tools that do not directly compete with Webflow. Could you confirm whether this described video-only use is covered by the Standard License, or whether you require written consent or additional conditions? We will preserve GSAP notices and identify its separate license.

Thank you.
