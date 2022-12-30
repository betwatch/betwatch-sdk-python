patch-publish:
	- hatch version patch
	- hatch build
	- hatch publish
