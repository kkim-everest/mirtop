"""This directory is setup with configurations to run the main functional test.

Inspired in bcbio-nextgen code
"""
import os
import subprocess
import unittest
import shutil
import contextlib
import collections
import functools

from nose import SkipTest
from nose.plugins.attrib import attr
import yaml


class FunctionsTest(unittest.TestCase):
    """Setup a full automated analysis and run the pipeline.
    """
    @attr(database=True)
    def test_database(self):
        from mirtop.mirna import mapper
        db = mapper.guess_database("data/examples/annotate/hsa.gff3")
        print "Database is %s" % db
        if db != "miRBasev21":
            raise ValueError("%s not eq to miRBasev21" % db)

    @attr(read=True)
    def test_read(self):
        from mirtop.mirna import mapper, fasta
        from mirtop.libs import logger
        logger.initialize_logger("test_read_files", True, True)
        map_mir = mapper.read_gtf_to_precursor("data/examples/annotate/hsa.gff3")
        print map_mir
        if map_mir["hsa-let-7a-1"]["hsa-let-7a-5p"][0] != 5:
            raise ValueError("GFF is not loaded correctly.")
        fasta_precursor = fasta.read_precursor("data/examples/annotate/hairpin.fa", "hsa")
        # read data/aligments/let7-perfect.bam
        return True

    @attr(read_genomic=True)
    def test_read_genomic(self):
        from mirtop.mirna import mapper, fasta
        from mirtop.libs import logger
        logger.initialize_logger("test_read_files", True, True)
        map_mir = mapper.read_gtf_to_mirna("data/examples/annotate/hsa.gff3")
        print map_mir
        # if map_mir["hsa-let-7a-1"]["hsa-let-7a-5p"][0] != 5:
        #    raise ValueError("GFF is not loaded correctly.")
        return True

    @attr(code=True)
    def test_code(self):
        """testing code correction function"""
        from mirtop.mirna.realign import make_id, read_id
        def _convert(s, test, reverse = False):
            code = read_id(s) if reverse else make_id(s)
            if code != test:
                raise ValueError("%s didn't result on %s but in %s" % (s, test, code))

        _convert("AAACCCTTTGGG", "@#%$")
        _convert("AAACCCTTTGGGA", "@#%$@2")
        _convert("AAACCCTTTGGGAT", "@#%$g1")
        _convert("@#%$", "AAACCCTTTGGG", True)
        _convert("@#%$@2", "AAACCCTTTGGGA", True)
        _convert("@#%$g1", "AAACCCTTTGGGAT", True)

    @attr(cigar=True)
    def test_cigar(self):
        """testing cigar correction function"""
        cigar = [[0, 14], [1, 1], [0, 5]]
        from mirtop.mirna.realign import cigar_correction, make_cigar, cigar2snp, expand_cigar
        fixed = cigar_correction(cigar, "AAAAGCTGGGTTGAGGAGGA", "AAAAGCTGGGTTGAGAGGA")
        if not fixed[0] == "AAAAGCTGGGTTGAGGAGGA":
            raise ValueError("Sequence 1 is not right.")
        if not fixed[1] == "AAAAGCTGGGTTGA-GAGGA":
            raise ValueError("Sequence 2 is not right.")
        if not make_cigar("AAA-AAATAAA", "AGACAAA-AAA") == "MAMD3MI3M":
            raise ValueError("Cigar not eq to MAMD3MI3M: %s" % make_cigar("AAA-AAATAAA", "AGACAAA-AAA"))
        # test expand cigar
        if not expand_cigar("3MA3M") == "MMMAMMM":
            raise ValueError("Cigar 3MA3M not eqaul to MMMAMMM but to %s" % expand_cigar("3MA3M"))
        # test cigar to snp
        if not cigar2snp("3MA3M", "AAATCCC")[0] == [3, "A", "T"]:
            raise ValueError("3MA3M not equal AAATCCC but %s" % cigar2snp("3MA3M", "AAATCCC"))

    @attr(locala=True)
    def test_locala(self):
        """testing pairwise alignment"""
        from mirtop.mirna.realign import align
        print "\nExamples of perfect match, deletion, mutation"
        print align("TGAGGTAGTAGGTTGTATAGTT", "TGAGGTAGTAGGTTGTATAGTT")[0]
        print align("TGAGGTGTAGGTTGTATAGTT", "TGAGGTAGTAGGTTGTATAGTT")[0]
        print align("TGAGGTAGTAGGCTGTATAGTT", "TGAGGTAGTAGGTTGTATAGTT")[0]

    @attr(reverse=True)
    def test_reverse(self):
        """Test reverse complement function"""
        from mirtop.mirna.realign import reverse_complement
        print "Testing ATGC complement"
        if "GCAT" != reverse_complement("ATGC"):
            logger.error("ATGC complement is not: %s" % reverse_complement("ATGC"))

    @attr(merge=True)
    def test_merge(self):
        """Test merge functions"""
        from mirtop.gff import merge
        if merge._chrom("hsa-let-7a-5p\tmiRBasev21\tisomiR\t4\t25") != "hsa-let-7a-5p":
            raise ValueError("Chrom should be hsa-let-7a-5p.")
        if merge._start("hsa-let-7a-5p\tmiRBasev21\tisomiR\t4\t25") != "4":
            raise ValueError("Start should be 4.")
        expression =merge._convert_to_string({'s': 1, 'x': 2}, ['s', 'x'])
        print merge._fix("hsa-let-7a-5p\tmiRBasev21\tisomiR\t4\t25\t0\t+\t.\tRead hsa-let-7a-1_hsa-let-7a-5p_5:26_-1:-1_mut:null_add:null_x861; UID bhJJ5WJL2; Name hsa-let-7a-5p; Parent hsa-let-7a-1; Variant iso_5p:+1,iso_3p:-1; Cigar 22M; Expression 861; Filter Pass; Hits 1;", expression)
        if expression != " Expression 1,2":
            raise ValueError("This is wrong: %s" % expression)

    @attr(alignment=True)
    def test_alignment(self):
        """testing alignments function"""
        from mirtop.libs import logger
        logger.initialize_logger("test", True, True)
        logger = logger.getLogger(__name__)
        from mirtop.mirna import fasta, mapper
        precursors = fasta.read_precursor("data/examples/annotate/hairpin.fa", "hsa")
        matures = mapper.read_gtf_to_precursor("data/examples/annotate/hsa.gff3")
        # matures = mirtop.mirna.read_mature("data/examples/annotate/mirnas.gff", "hsa")
        def annotate(fn, precursors, matures):
            from mirtop.bam import bam
            from mirtop.gff import body
            from mirtop.mirna import annotate
            reads = bam.read_bam(fn, precursors)
            ann = annotate.annotate(reads, matures, precursors)
            gff = body.create(ann, "miRBase21", "example")
        print "\nlast1D\n"
        annotate("data/aligments/let7-last1D.sam", precursors, matures)
        #mirna TGAGGTAGTAGGTTGTATAGTT
        #seq   AGAGGTAGTAGGTTGTA
        print "\n1D\n"
        annotate("data/aligments/let7-1D.sam", precursors, matures)
        #mirna TGAGGTAG-TAGGTTGTATAGTT
        #seq   TGAGGTAGGTAGGTTGTATAGTTA
        print "\nlast7M1I\n"
        annotate("data/aligments/let7-last7M1I.sam", precursors, matures)
        #mirna TGAGGTAGTAGGTTGTATAGTT
        #seq   TGAGGTAGTAGGTTGTA-AGT
        print "\nmiddle1D\n"
        annotate("data/aligments/let7-middle1D.sam", precursors, matures)
        #mirna TGAGGTAGTAGGTTGTATAGTT
        #seq   TGAGGTAGTAGGTTGTATAGTT
        print "\nperfect\n"
        annotate("data/aligments/let7-perfect.sam", precursors, matures)
        #mirna TGAGGTAGTAGGTTGTATAGTT
        #seq   TGAGGTAGTAGGTTGTATAG (3tt 3TT)
        print "\ntriming\n"
        annotate ("data/aligments/let7-triming.sam", precursors, matures)

    @attr(seqbuster=True)
    def test_seqbuster(self):
        """testing reading seqbuster files function"""
        from mirtop.libs import logger
        logger.initialize_logger("test", True, True)
        logger = logger.getLogger(__name__)
        from mirtop.mirna import fasta, mapper
        precursors = fasta.read_precursor("data/examples/annotate/hairpin.fa", "hsa")
        matures = mapper.read_gtf_to_precursor("data/examples/annotate/hsa.gff3")
        def annotate(fn, precursors, matures):
            from mirtop.importer import seqbuster
            from mirtop.bam import bam
            from mirtop.mirna import annotate
            from mirtop.gff import body
            reads = seqbuster.read_file(fn, precursors)
            ann = annotate.annotate(reads, matures, precursors)
            body = body.create(ann, "miRBase21", "Example")
            return True
        print "\nperfect\n"
        annotate("data/examples/seqbuster/reads20.mirna", precursors, matures)
        print "\naddition\n"
        annotate("data/examples/seqbuster/readsAdd.mirna", precursors, matures)

    @attr(srnabench=True)
    def test_srnabench(self):
        """testing reading seqbuster files function"""
        from mirtop.libs import logger
        logger.initialize_logger("test", True, True)
        logger = logger.getLogger(__name__)
        from mirtop.mirna import fasta, mapper
        precursors = fasta.read_precursor("data/examples/annotate/hairpin.fa", "hsa")
        matures = mapper.read_gtf_to_precursor("data/examples/annotate/hsa.gff3")
        def annotate(fn, precursors, matures):
            from mirtop.importer import srnabench
            from mirtop.bam import bam
            from mirtop.mirna import annotate
            from mirtop.gff import body
            reads = srnabench.read_file(fn, precursors)
            ann = annotate.annotate(reads, matures, precursors)
            body = body.create(ann, "miRBase21", "Example")
            return True
        print "\nsRNAbench\n"
        annotate("data/examples/srnabench", precursors, matures)

    @attr(prost=True)
    def test_prost(self):
        """testing reading prost files function"""
        from mirtop.libs import logger
        logger.initialize_logger("test", True, True)
        logger = logger.getLogger(__name__)
        from mirtop.mirna import fasta, mapper
        precursors = fasta.read_precursor("data/examples/annotate/hairpin.fa", "hsa")
        matures = mapper.read_gtf_to_precursor("data/examples/annotate/hsa.gff3")
        def annotate(fn, precursors, matures):
            from mirtop.importer import prost
            from mirtop.bam import bam
            from mirtop.mirna import annotate
            from mirtop.gff import body
            reads = prost.read_file(fn, precursors, "data/examples/annotate/hsa.gff3")
            ann = annotate.annotate(reads, matures, precursors)
            gff = body.create(ann, "miRBase21", "prost")
            return True
        print "\nPROST\n"
        annotate("data/examples/prost/example.mincount3.txt", precursors, matures)

    @attr(gff=True)
    def test_gff(self):
        """testing GFF function"""
        from mirtop.libs import logger
        from mirtop.mirna import mapper, fasta
        from mirtop.gff import body, header
        logger.initialize_logger("test", True, True)
        logger = logger.getLogger(__name__)
        precursors = fasta.read_precursor("data/examples/annotate/hairpin.fa", "hsa")
        # depend on https://github.com/miRTop/mirtop/issues/6
        matures = mapper.read_gtf_to_precursor("data/examples/annotate/hsa.gff3")
        # matures = mirtop.mirna.read_mature("data/examples/annotate/mirnas.gff", "hsa")
        from mirtop.bam import bam
        from mirtop.mirna import annotate
        bam_fn = "data/aligments/let7-perfect.sam"
        reads = bam.read_bam(bam_fn, precursors)
        ann = annotate.annotate(reads, matures, precursors)
        h = header.create(bam_fn, ["example"], "miRBase21")
        gff = body.create(ann, "miRBase21", "example")
        return True

    @attr(collapse=True)
    def test_collapse(self):
        """testing GFF function"""
        from mirtop.libs import logger
        from mirtop.mirna import mapper, fasta
        from mirtop.gff import body, header
        logger.initialize_logger("test", True, True)
        logger = logger.getLogger(__name__)
        precursors = fasta.read_precursor("data/examples/annotate/hairpin.fa", "hsa")
        # depend on https://github.com/miRTop/mirtop/issues/6
        matures = mapper.read_gtf_to_precursor("data/examples/annotate/hsa.gff3")
        # matures = mirtop.mirna.read_mature("data/examples/annotate/mirnas.gff", "hsa")
        from mirtop.bam import bam
        from mirtop.mirna import annotate
        bam_fn = "data/aligments/collapsing-isomirs.sam"
        reads = bam.read_bam(bam_fn, precursors)
        ann = annotate.annotate(reads, matures, precursors)
        fn = bam_fn + ".gff"
        h = header.create(bam_fn, ["example"], "miRBase21")
        gff = body.create(ann, "miRBase21", "example")
        print gff
        return True


