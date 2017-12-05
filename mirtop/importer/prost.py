""" Read prost files"""

import traceback
import os.path as op
import os
import re
import shutil
import pandas as pd
import pysam
from collections import defaultdict

from mirtop.mirna import mapper
from mirtop.libs import do
from mirtop.libs.utils import file_exists
import mirtop.libs.logger as mylog
from mirtop.mirna.realign import isomir, hits
from mirtop.bam import filter

logger = mylog.getLogger(__name__)

def header():
    return ""

def read_file(fn, precursors, mirna_gtf):
    """
    read bam file and perform realignment of hits
    """
    reads = defaultdict(hits)
    map_mir = mapper.read_gtf_to_mirna(mirna_gtf)
    non_mirna = 0
    non_chromosome_mirna = 0
    outside_mirna = 0
    lines_read = 0
    with open(fn) as handle:
        handle.readline()
        for line in handle:
            lines_read += 1
            cols = line.strip().split("\t")
            query_name = cols[0]
            query_sequence = cols[0]
            if len(cols) < 12:
                non_mirna += 1
                continue
            miRNA = cols[11]
            if not miRNA:
                continue
            if query_name not in reads and query_sequence == None:
                continue
            if query_sequence and query_sequence.find("N") > -1:
                continue
            if query_name not in reads:
                reads[query_name].set_sequence(query_sequence)
                reads[query_name].counts = int(cols[9])
            for loc in cols[5].split(";"):
                if loc.find("-") < 0:
                    non_chromosome_mirna += 1
                    continue
                chrom = loc.split(":")[0]
                start, end = loc.split(":")[1].split("-")
                chrom, reference_start =  _genomic2transcript(map_mir[miRNA], chrom, int(start))
                if not chrom:
                    non_chromosome_mirna += 1
                    continue
                # reference_start = int(cols[4]) - 1
                logger.debug("\nPROST::NEW::query: {query_sequence}\n"
                             "  precursor {chrom}\n"
                             "  name:  {query_name}\n"
                             "  start: {start}\n"
                             "  reference_start: {reference_start}\n"
                             "  mirna: {miRNA}".format(**locals()))
                # logger.debug("PROST:: cigar {cigar}".format(**locals()))
                iso = isomir()
                iso.align = line
                iso.set_pos(reference_start, len(reads[query_name].sequence))
                logger.debug("PROST:: start %s end %s" % (iso.start, iso.end))
                if len(precursors[chrom]) < reference_start + len(reads[query_name].sequence):
                    outside_mirna += 1
                    continue
                iso.subs, iso.add, iso.cigar = filter.tune(reads[query_name].sequence,
                                                           precursors[chrom],
                                                           reference_start, None)
                logger.debug("PROST::After tune start %s end %s" % (iso.start, iso.end))
                #if len(iso.subs) < 2:
                reads[query_name].set_precursor(chrom, iso)
    logger.info("Lines loaded: %s" % lines_read)
    logger.info("Skipped lines because non miRNA in line: %s" % non_mirna)
    logger.info("Skipped lines because non chromosome in GTF: %s" % non_chromosome_mirna)
    logger.info("Skipped lines because outside precursor: %s" % outside_mirna)
    logger.info("Hits: %s" % len(reads))
    return reads

def _genomic2transcript(code, chrom, pos):
    for ref in code:
        if _is_chrom(chrom, code[ref][0]):
            if _is_inside(pos, code[ref][1:3]):
                return [ref, _transcript(pos, code[ref][1:4])]
    return [None, None]

def _is_chrom(chrom, annotated):
    logger.debug("TRANSCRIPT::CHROM::read position %s and db position %s" % (chrom, annotated))
    if chrom == annotated:
        return True
    if chrom == annotated.replace("chr", ""):
        return True
    return False

def _is_inside(pos, annotated):
    logger.debug("TRANSCRIPT::INSIDE::read position %s and db position %s" % (pos, annotated))
    if pos > annotated[0] and pos < annotated[1]:
        return True
    return False

def _transcript(pos, annotated):
    logger.debug("TRANSCRIPT::TRANSCRIPT::read position %s and db position %s" % (pos, annotated))
    if annotated[2] == "+":
        return pos - annotated[0]
    elif annotated[2] == "-":
        return annotated[1] - pos
    raise ValueError("Strand information is incorrect %s" % annotated[3])
