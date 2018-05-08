#!/usr/bin/env python

# Hamming distance analysis of SSCSs
#
# Author: Monika Heinzl, Johannes-Kepler University Linz (Austria)
# Contact: monika.heinzl@edumail.at
#
# Takes at least one TABULAR file with tags before the alignment to the SSCS and optionally a second TABULAR file as input.
# The program produces a plot which shows a histogram of Hamming distances separated after family sizes,
# a family size distribution separated after Hamming distances for all (sample_size=0) or a given sample of SSCSs or SSCSs, which form a DCS.
# In additon, the tool produces HD and FSD plots for the difference between the HDs of both parts of the tags and for the chimeric reads
# and finally a CSV file with the data of the plots.
# It is also possible to perform the HD analysis with shortened tags with given sizes as input.
# The tool can run on a certain number of processors, which can be defined by the user.

# USAGE: python HDnew6_1Plot_FINAL.py filename --inputFile2 --sample_size int/0 --title_file outputFileName --sep "characterWhichSeparatesCSVFile" /
#        --only_DCS True --FamilySize3 True --subset_tag True --nproc int

import numpy
import itertools
import operator
import matplotlib.pyplot as plt
import os.path
import cPickle as pickle
from multiprocessing.pool import Pool
from functools import partial
from HDAnalysis_plots.plot_HDwithFSD import plotHDwithFSD
from HDAnalysis_plots.plot_FSDwithHD2 import plotFSDwithHD2
from HDAnalysis_plots.plot_HDwithinSeq_Sum2 import plotHDwithinSeq_Sum2
from HDAnalysis_plots.table_HD import createTableHD, createFileHD, createTableHDwithTags, createFileHDwithinTag
from HDAnalysis_plots.table_FSD import createTableFSD2, createFileFSD2
import argparse
import sys
import os
from matplotlib.backends.backend_pdf import PdfPages

def hamming(array1, array2):
    res = 99 * numpy.ones(len(array1))
    i = 0
    array2 = numpy.unique(array2)  # remove duplicate sequences to decrease running time
    for a in array1:
        dist = numpy.array([sum(itertools.imap(operator.ne, a, b)) for b in array2])  # fastest
        res[i] = numpy.amin(dist[dist > 0])  # pick min distance greater than zero
        #print(i)
        i += 1
    return res

def hamming_difference(array1, array2, mate_b):
    array2 = numpy.unique(array2)  # remove duplicate sequences to decrease running time
    array1_half = numpy.array([i[0:(len(i)) / 2] for i in array1]) # mate1 part1
    array1_half2 = numpy.array([i[len(i) / 2:len(i)] for i in array1]) # mate1 part 2

    array2_half = numpy.array([i[0:(len(i)) / 2] for i in array2]) # mate2 part1
    array2_half2 = numpy.array([i[len(i) / 2:len(i)] for i in array2])  # mate2 part2

    diff11 = []
    relativeDiffList = []
    ham1 = []
    ham2 = []
    min_valueList = []
    min_tagsList = []
    diff11_zeros = []
    min_tagsList_zeros = []
    i = 0 # counter, only used to see how many HDs of tags were already calculated
    if mate_b is False: # HD calculation for all a's
        half1_mate1 = array1_half
        half2_mate1 = array1_half2
        half1_mate2 = array2_half
        half2_mate2 = array2_half2
    elif mate_b is True: # HD calculation for all b's
        half1_mate1 = array1_half2
        half2_mate1 = array1_half
        half1_mate2 = array2_half2
        half2_mate2 = array2_half

    for a, b, tag in zip(half1_mate1, half2_mate1, array1):
        ## exclude identical tag from array2, to prevent comparison to itself
        sameTag = numpy.where(array2 == tag)
        indexArray2 = numpy.arange(0, len(array2), 1)
        index_withoutSame = numpy.delete(indexArray2, sameTag)  # delete identical tag from the data

        # all tags without identical tag
        array2_half_withoutSame = half1_mate2[index_withoutSame]
        array2_half2_withoutSame = half2_mate2[index_withoutSame]
        #array2_withoutSame = array2[index_withoutSame] # whole tag (=not splitted into 2 halfs)

        dist = numpy.array([sum(itertools.imap(operator.ne, a, c)) for c in
                            array2_half_withoutSame])  # calculate HD of "a" in the tag to all "a's" or "b" in the tag to all "b's"
        min_index = numpy.where(dist == dist.min()) # get index of min HD
        min_value = dist[min_index]  # get minimum HDs
        min_tag_half2 = array2_half2_withoutSame[min_index]  # get all "b's" of the tag or all "a's" of the tag with minimum HD
        #min_tag = array2_withoutSame[min_index] # get whole tag with min HD

        dist2 = numpy.array([sum(itertools.imap(operator.ne, b, e)) for e in
                             min_tag_half2])  # calculate HD of "b" to all "b's" or "a" to all "a's"
        for d_1, d_2 in zip(min_value, dist2):
            if mate_b is True:  # half2, corrects the variable of the HD from both halfs if it is a or b
                d = d_2
                d2 = d_1
            else:  # half1, corrects the variable of the HD from both halfs if it is a or b
                d = d_1
                d2 = d_2
            min_valueList.append(d + d2)
            min_tagsList.append(tag)
            ham1.append(d)
            ham2.append(d2)
            difference1 = abs(d - d2)
            diff11.append(difference1)
            rel_difference = round(float(difference1) / (d + d2), 1)
            relativeDiffList.append(rel_difference)

            #### tags which have identical parts:
            if d == 0 or d2 == 0:
                min_tagsList_zeros.append(tag)
                difference1_zeros = abs(d - d2)
                diff11_zeros.append(difference1_zeros)
        #print(i)
        i += 1
    return ([diff11, ham1, ham2, min_valueList, min_tagsList, relativeDiffList, diff11_zeros, min_tagsList_zeros])

def readFileReferenceFree(file):
    with open(file, 'r') as dest_f:
        data_array = numpy.genfromtxt(dest_f, skip_header=0, delimiter='\t', comments='#', dtype='string')
        integers = numpy.array(data_array[:, 0]).astype(int)
        return(integers, data_array)

def hammingDistanceWithFS(quant, ham):
    quant = numpy.asarray(quant)
    maximum = max(ham)
    minimum = min(ham)
    ham = numpy.asarray(ham)

    singletons = numpy.where(quant == 1)[0]
    data = ham[singletons]

    hd2 = numpy.where(quant == 2)[0]
    data2 = ham[hd2]

    hd3 = numpy.where(quant == 3)[0]
    data3 = ham[hd3]

    hd4 = numpy.where(quant == 4)[0]
    data4 = ham[hd4]

    hd5 = numpy.where((quant >= 5) & (quant <= 10))[0]
    data5 = ham[hd5]

    hd6 = numpy.where(quant > 10)[0]
    data6 = ham[hd6]

    list1 = [data, data2, data3, data4, data5, data6]
    return(list1, maximum, minimum)

def familySizeDistributionWithHD(fs, ham, diff=False, rel = True):
    hammingDistances = numpy.unique(ham)
    fs = numpy.asarray(fs)

    ham = numpy.asarray(ham)
    bigFamilies2 = numpy.where(fs > 19)[0]
    if len(bigFamilies2) != 0:
        fs[bigFamilies2] = 20
    maximum = max(fs)
    minimum = min(fs)
    if diff is True:
        hd0 = numpy.where(ham == 0)[0]
        data0 = fs[hd0]

    if rel is True:
        hd1 = numpy.where(ham == 0.1)[0]
    else:
        hd1 = numpy.where(ham == 1)[0]
    data = fs[hd1]

    if rel is True:
        hd2 = numpy.where(ham == 0.2)[0]
    else:
        hd2 = numpy.where(ham == 2)[0]
    data2 = fs[hd2]

    if rel is True:
        hd3 = numpy.where(ham == 0.3)[0]
    else:
        hd3 = numpy.where(ham == 3)[0]
    data3 = fs[hd3]

    if rel is True:
        hd4 = numpy.where(ham == 0.4)[0]
    else:
        hd4 = numpy.where(ham == 4)[0]
    data4 = fs[hd4]

    if rel is True:
        hd5 = numpy.where((ham >= 0.5) & (ham <= 0.8))[0]
    else:
        hd5 = numpy.where((ham >= 5) & (ham <= 8))[0]
    data5 = fs[hd5]

    if rel is True:
        hd6 = numpy.where(ham > 0.8)[0]
    else:
        hd6 = numpy.where(ham > 8)[0]
    data6 = fs[hd6]

    if diff is True:
        list1 = [data0,data, data2, data3, data4, data5, data6]
    else:
        list1 = [data, data2, data3, data4, data5, data6]

    return(list1, hammingDistances, maximum, minimum)

def make_argparser():
    parser = argparse.ArgumentParser(description='Hamming distance analysis of duplex sequencing data')
    parser.add_argument('inputFile',
                        help='Tabular File with three columns: ab or ba, tag and family size.')
    parser.add_argument('--inputName1')
    parser.add_argument('--inputFile2',default=None,
                        help='Tabular File with three columns: ab or ba, tag and family size.')
    parser.add_argument('--inputName2')
    parser.add_argument('--sample_size', default=1000,type=int,
                        help='Sample size of Hamming distance analysis.')
    parser.add_argument('--sep', default=",",
                        help='Separator in the csv file.')
    parser.add_argument('--subset_tag', default=0,type=int,
                        help='The tag is shortened to the given number.')
    parser.add_argument('--nproc', default=4,type=int,
                        help='The tool runs with the given number of processors.')
    parser.add_argument('--only_DCS', action="store_false",  # default=False, type=bool,
                        help='Only tags of the DCSs are included in the HD analysis')

    parser.add_argument('--minFS', default=1, type=int,
                        help='Only tags, which have a family size greater or equal than specified, are included in the HD analysis')
    parser.add_argument('--maxFS', default=0, type=int,
                        help='Only tags, which have a family size smaller or equal than specified, are included in the HD analysis')

    parser.add_argument('--output_csv', default="data.csv", type=str,
                        help='Name of the csv file.')
    parser.add_argument('--output_pdf', default="data.pdf", type=str,
                        help='Name of the pdf file.')
    parser.add_argument('--output_pdf2', default="data2.pdf", type=str,
                        help='Name of the pdf file.')
    parser.add_argument('--output_csv2', default="data2.csv", type=str,
                        help='Name of the csv file.')

    return parser

def Hamming_Distance_Analysis(argv):
    parser = make_argparser()
    args = parser.parse_args(argv[1:])

    file1 = args.inputFile
    name1 = args.inputName1

    file2 = args.inputFile2
    name2 = args.inputName2

    index_size = args.sample_size
    title_savedFile_pdf = args.output_pdf
    title_savedFile_pdf2 = args.output_pdf2

    title_savedFile_csv = args.output_csv
    title_savedFile_csv2 = args.output_csv2

    sep = args.sep
    onlyDuplicates = args.only_DCS
    minFS = args.minFS
    maxFS = args.maxFS

    subset = args.subset_tag
    nproc = args.nproc

    ### input checks
    if index_size < 0:
        print("index_size is a negative integer.")
        exit(2)

    if nproc <= 0:
        print("nproc is smaller or equal zero")
        exit(3)

    if type(sep) is not str or len(sep)>1:
        print("sep must be a single character.")
        exit(4)

    if subset < 0:
        print("subset_tag is smaller or equal zero.")
        exit(5)

    ### PLOT ###
    plt.rcParams['axes.facecolor'] = "E0E0E0"  # grey background color
    plt.rcParams['xtick.labelsize'] = 12
    plt.rcParams['ytick.labelsize'] = 12
    plt.rcParams['patch.edgecolor'] = "#000000"
    plt.rc('figure', figsize=(11.69, 8.27))  # A4 format

    if file2 != str(None):
        files = [file1, file2]
        name1 = name1.split(".tabular")[0]
        name2 = name2.split(".tabular")[0]
        names = [name1, name2]
        pdf_files = [title_savedFile_pdf, title_savedFile_pdf2]
        csv_files = [title_savedFile_csv, title_savedFile_csv2]
    else:
        files = [file1]
        name1 = name1.split(".tabular")[0]
        names = [name1]
        pdf_files = [title_savedFile_pdf]
        csv_files = [title_savedFile_csv]

    print(type(onlyDuplicates))
    print(onlyDuplicates)

    for f, name_file, pdf_f, csv_f in zip(files, names, pdf_files, csv_files):
        with open(csv_f, "w") as output_file, PdfPages(pdf_f) as pdf:
            print("dataset: ", name_file)
            integers, data_array = readFileReferenceFree(f)
            data_array = numpy.array(data_array)
            int_f = numpy.array(data_array[:, 0]).astype(int)
            data_array = data_array[numpy.where(int_f >= minFS)]
            integers = integers[integers >= minFS]

            # select family size for tags
            if maxFS > 0:
                int_f2 = numpy.array(data_array[:, 0]).astype(int)
                data_array = data_array[numpy.where(int_f2 <= maxFS)]
                integers = integers[integers <= maxFS]

            print("min FS", min(integers))
            print("max FS", max(integers))

            tags = data_array[:, 2]
            seq = data_array[:, 1]

            if onlyDuplicates is True:
                # find all unique tags and get the indices for ALL tags, but only once
                u, index_unique, c = numpy.unique(numpy.array(seq), return_counts=True, return_index=True)
                d = u[c > 1]

                # get family sizes, tag for duplicates
                duplTags_double = integers[numpy.in1d(seq, d)]
                duplTags = duplTags_double[0::2]  # ab of DCS
                duplTagsBA = duplTags_double[1::2]  # ba of DCS

                duplTags_tag = tags[numpy.in1d(seq, d)][0::2]  # ab
                duplTags_seq = seq[numpy.in1d(seq, d)][0::2]  # ab - tags

                data_array = numpy.column_stack((duplTags, duplTags_seq))
                data_array = numpy.column_stack((data_array, duplTags_tag))
                integers = numpy.array(data_array[:, 0]).astype(int)
                print("DCS in whole dataset", len(data_array))

            ## HD analysis for a subset of the tag
            if subset > 0:
                tag1 = numpy.array([i[0:(len(i)) / 2] for i in data_array[:, 1]])
                tag2 = numpy.array([i[len(i) / 2:len(i)] for i in data_array[:, 1]])

                flanking_region_float = float((len(tag1[0]) - subset)) / 2
                flanking_region = int(flanking_region_float)
                if flanking_region_float % 2 == 0:
                    tag1_shorten = numpy.array([i[flanking_region:len(i) - flanking_region] for i in tag1])
                    tag2_shorten = numpy.array([i[flanking_region:len(i) - flanking_region] for i in tag2])
                else:
                    flanking_region_rounded = int(round(flanking_region, 1))
                    flanking_region_rounded_end = len(tag1[0]) - subset - flanking_region_rounded
                    tag1_shorten = numpy.array(
                        [i[flanking_region:len(i) - flanking_region_rounded_end] for i in tag1])
                    tag2_shorten = numpy.array(
                        [i[flanking_region:len(i) - flanking_region_rounded_end] for i in tag2])

                data_array_tag = numpy.array([i + j for i, j in zip(tag1_shorten, tag2_shorten)])
                data_array = numpy.column_stack((data_array[:, 0], data_array_tag, data_array[:, 2]))

            print("length of tag= ", len(data_array[0, 1]))
            # select sample: if no size given --> all vs. all comparison
            if index_size == 0:
                result = numpy.arange(0, len(data_array), 1)
            else:
                result = numpy.random.choice(len(integers), size=index_size,
                                             replace=False)  # array of random sequences of size=index.size

           # with open("index_result1_{}.pkl".format(app_f), "wb") as o:
            #    pickle.dump(result, o, pickle.HIGHEST_PROTOCOL)

            # comparison random tags to whole dataset
            result1 = data_array[result, 1]  # random tags
            result2 = data_array[:, 1]  # all tags
            print("size of the whole dataset= ", len(result2))
            print("sample size= ", len(result1))

            # HD analysis of whole tag
            proc_pool = Pool(nproc)
            chunks_sample = numpy.array_split(result1, nproc)
            ham = proc_pool.map(partial(hamming, array2=result2), chunks_sample)
            proc_pool.close()
            proc_pool.join()
            ham = numpy.concatenate(ham).astype(int)
          #  with open("HD_whole dataset_{}.txt".format(app_f), "w") as output_file1:
           #     for h, tag in zip(ham, result1):
            #        output_file1.write("{}\t{}\n".format(tag, h))

            # HD analysis for chimeric reads
            proc_pool_b = Pool(nproc)
            diff_list_a = proc_pool_b.map(partial(hamming_difference, array2=result2, mate_b=False), chunks_sample)
            diff_list_b = proc_pool_b.map(partial(hamming_difference, array2=result2, mate_b=True), chunks_sample)
            proc_pool_b.close()
            proc_pool_b.join()
            diff = numpy.concatenate((numpy.concatenate([item[0] for item in diff_list_a]),
                                      numpy.concatenate([item_b[0] for item_b in diff_list_b]))).astype(int)
            HDhalf1 = numpy.concatenate((numpy.concatenate([item[1] for item in diff_list_a]),
                                         numpy.concatenate([item_b[1] for item_b in diff_list_b]))).astype(int)
            HDhalf2 = numpy.concatenate((numpy.concatenate([item[2] for item in diff_list_a]),
                                         numpy.concatenate([item_b[2] for item_b in diff_list_b]))).astype(int)
            minHDs = numpy.concatenate((numpy.concatenate([item[3] for item in diff_list_a]),
                                        numpy.concatenate([item_b[3] for item_b in diff_list_b]))).astype(int)
            minHD_tags = numpy.concatenate((numpy.concatenate([item[4] for item in diff_list_a]),
                                            numpy.concatenate([item_b[4] for item_b in diff_list_b])))
            rel_Diff = numpy.concatenate((numpy.concatenate([item[5] for item in diff_list_a]),
                                          numpy.concatenate([item_b[5] for item_b in diff_list_b])))
            diff_zeros = numpy.concatenate((numpy.concatenate([item[6] for item in diff_list_a]),
                                            numpy.concatenate([item_b[6] for item_b in diff_list_b]))).astype(int)
            minHD_tags_zeros = numpy.concatenate((numpy.concatenate([item[7] for item in diff_list_a]),
                                                  numpy.concatenate([item_b[7] for item_b in diff_list_b])))

         #   with open("HD_within tag_{}.txt".format(app_f), "w") as output_file2:
          #      for d, s1, s2, hd, rel_d, tag in zip(diff, HDhalf1, HDhalf2, minHDs, rel_Diff, minHD_tags):
           #         output_file2.write(
            #            "{}\t{}\t{}\t{}\t{}\t{}\n".format(tag, hd, s1, s2, d, rel_d))

            lenTags = len(data_array)

            quant = numpy.array(data_array[result, 0]).astype(int)  # family size for sample of tags
            seq = numpy.array(data_array[result, 1])  # tags of sample
            ham = numpy.asarray(ham)  # HD for sample of tags

            if onlyDuplicates is True:  # ab and ba strands of DCSs
                quant = numpy.concatenate((quant, duplTagsBA[result]))
                seq = numpy.tile(seq, 2)
                ham = numpy.tile(ham, 2)

            # prepare data for different kinds of plots
            list1, maximumX, minimumX = hammingDistanceWithFS(quant, ham)  # histogram of HDs separated after FS
            # distribution of FSs separated after HD
            familySizeList1, hammingDistances, maximumXFS, minimumXFS = familySizeDistributionWithHD(quant, ham,
                                                                                                     rel=False)

            ## get FS for all tags with min HD of analysis of chimeric reads
            # there are more tags than sample size in the plot, because one tag can have multiple minimas
            seqDic = dict(zip(seq, quant))
            lst_minHD_tags = []
            for i in minHD_tags:
                lst_minHD_tags.append(seqDic.get(i))

            # histogram with absolute and relative difference between HDs of both parts of the tag
            listDifference1, maximumXDifference, minimumXDifference = hammingDistanceWithFS(lst_minHD_tags, diff)
            listRelDifference1, maximumXRelDifference, minimumXRelDifference = hammingDistanceWithFS(lst_minHD_tags,
                                                                                                     rel_Diff)

            # family size distribution separated after the difference between HDs of both parts of the tag
            familySizeList1_diff, hammingDistances_diff, maximumXFS_diff, minimumXFS_diff = familySizeDistributionWithHD(
                lst_minHD_tags, diff, diff=True, rel=False)
            familySizeList1_reldiff, hammingDistances_reldiff, maximumXFS_reldiff, minimumXFS_reldiff = familySizeDistributionWithHD(
                lst_minHD_tags, rel_Diff, diff=True, rel=True)

            # chimeric read analysis: tags which have HD=0 in one of the halfs
            if len(minHD_tags_zeros) != 0:
                lst_minHD_tags_zeros = []
                for i in minHD_tags_zeros:
                    lst_minHD_tags_zeros.append(seqDic.get(i))  # get family size for tags of chimeric reads

                # histogram with HD of non-identical half
                listDifference1_zeros, maximumXDifference_zeros, minimumXDifference_zeros = hammingDistanceWithFS(
                    lst_minHD_tags_zeros, diff_zeros)
                # family size distribution of non-identical half
                familySizeList1_diff_zeros, hammingDistances_diff_zeros, maximumXFS_diff_zeros, minimumXFS_diff_zeros = familySizeDistributionWithHD(
                    lst_minHD_tags_zeros, diff_zeros, diff=False, rel=False)

            #####################################################################################################################
            ##################         plot Hamming Distance with Family size distribution         ##############################
            #####################################################################################################################
            plotHDwithFSD(list1=list1, maximumX=maximumX, minimumX=minimumX, pdf=pdf,
                          subtitle="Overall hamming distance with separation after family size", title_file1=name_file,
                          lenTags=lenTags,xlabel="Hamming distance")

            ##########################       Plot FSD with separation after HD       ###############################################
            ########################################################################################################################
            plotFSDwithHD2(familySizeList1, maximumXFS, minimumXFS,
                           quant=quant, subtitle="Family size distribution with separation after hamming distance",
                           pdf=pdf,relative=False, title_file1=name_file, diff=False)

            ##########################       Plot difference between HD's separated after FSD       ##########################################
            ########################################################################################################################
            plotHDwithFSD(listDifference1, maximumXDifference, minimumXDifference, pdf=pdf,
                          subtitle="Delta Hamming distances within tags with separation after family size",
                          title_file1=name_file, lenTags=lenTags,
                          xlabel="absolute delta Hamming distance", relative=False)

            plotHDwithFSD(listRelDifference1, maximumXRelDifference, minimumXRelDifference, pdf=pdf,
                          subtitle="Relative delta Hamming distances within tags with separation after family size",
                          title_file1=name_file, lenTags=lenTags,
                          xlabel="relative delta Hamming distance", relative=True)

            ####################       Plot FSD separated after difference between HD's        #####################################
            ########################################################################################################################
            plotFSDwithHD2(familySizeList1_diff, maximumXFS_diff, minimumXFS_diff,
                           subtitle="Family size distribution with separation after delta Hamming distances within the tags",
                           pdf=pdf,relative=False, diff=True, title_file1=name_file, quant=quant)

            plotFSDwithHD2(familySizeList1_reldiff, maximumXFS_reldiff, minimumXFS_reldiff, quant=quant, pdf=pdf,
                           subtitle="Family size distribution with separation after delta Hamming distances within the tags",
                           relative=True, diff=True, title_file1=name_file)

            ##########################       Plot HD within tags          ########################################################
            ######################################################################################################################
            plotHDwithinSeq_Sum2(HDhalf1, HDhalf2, minHDs, pdf=pdf, lenTags=lenTags, title_file1=name_file)

            # plots for chimeric reads
            if len(minHD_tags_zeros) != 0:
                ## HD
                plotHDwithFSD(listDifference1_zeros, maximumXDifference_zeros, minimumXDifference_zeros, pdf=pdf,
                              subtitle="Hamming Distance of the non-identical half with separation after family size"
                                       "\n(at least one half is identical with the half of the min. tag)\n",
                              title_file1=name_file, lenTags=lenTags,xlabel="Hamming distance", relative=False)

                ## FSD
                plotFSDwithHD2(familySizeList1_diff_zeros, maximumXFS_diff_zeros, minimumXFS_diff_zeros,
                               quant=quant, pdf=pdf,
                               subtitle="Family size distribution with separation after hamming distances from the non-identical half\n"
                                        "(at least one half is identical with the half of the min. tag)\n",
                               relative=False, diff=False, title_file1=name_file)

            ### print all data to a CSV file
            #### HD ####
            summary, sumCol = createTableHD(list1, "HD=")
            overallSum = sum(sumCol)  # sum of columns in table

            #### FSD ####
            summary5, sumCol5 = createTableFSD2(familySizeList1, diff=False)
            overallSum5 = sum(sumCol5)

            ### HD of both parts of the tag ####
            summary9, sumCol9 = createTableHDwithTags([numpy.array(minHDs), HDhalf1, HDhalf2])
            overallSum9 = sum(sumCol9)

            ## HD
            # absolute difference
            summary11, sumCol11 = createTableHD(listDifference1, "diff=")
            overallSum11 = sum(sumCol11)
            # relative difference and all tags
            summary13, sumCol13 = createTableHD(listRelDifference1, "diff=")
            overallSum13 = sum(sumCol13)

            ## FSD
            # absolute difference
            summary19, sumCol19 = createTableFSD2(familySizeList1_diff)
            overallSum19 = sum(sumCol19)
            # relative difference
            summary21, sumCol21 = createTableFSD2(familySizeList1_reldiff)
            overallSum21 = sum(sumCol21)

            # chimeric reads
            if len(minHD_tags_zeros) != 0:
                # absolute difference and tags where at least one half has HD=0
                summary15, sumCol15 = createTableHD(listDifference1_zeros, "diff=")
                overallSum15 = sum(sumCol15)
                # absolute difference and tags where at least one half has HD=0
                summary23, sumCol23 = createTableFSD2(familySizeList1_diff_zeros, diff=False)
                overallSum23 = sum(sumCol23)

            output_file.write("{}\n".format(f))
            output_file.write("number of tags per file{}{:,} (from {:,}) against {:,}\n\n".format(sep, len(
                numpy.concatenate(list1)), lenTags, lenTags))

            ### HD ###
            createFileHD(summary, sumCol, overallSum, output_file,
                         "Hamming distance with separation after family size: file1", sep)
            ### FSD ###
            createFileFSD2(summary5, sumCol5, overallSum5, output_file,
                           "Family size distribution with separation after hamming distances: file1", sep,
                           diff=False)

            count = numpy.bincount(quant)
            output_file.write("{}{}\n".format(sep, f))
            output_file.write("max. family size:{}{}\n".format(sep, max(quant)))
            output_file.write("absolute frequency:{}{}\n".format(sep, count[len(count) - 1]))
            output_file.write(
                "relative frequency:{}{}\n\n".format(sep, float(count[len(count) - 1]) / sum(count)))

            ### HD within tags ###
            output_file.write(
                "The hamming distances were calculated by comparing each half of all tags against the tag(s) with the minimum Hamming distance per half.\n"
                "It is possible that one tag can have the minimum HD from multiple tags, so the sample size in this calculation differs from the sample size entered by the user.\n")
            output_file.write(
                "file 1: actual number of tags with min HD = {:,} (sample size by user = {:,})\n".format(
                    len(numpy.concatenate(listDifference1)), len(numpy.concatenate(list1))))
            output_file.write("length of one part of the tag = {}\n\n".format(len(data_array[0, 1]) / 2))

            createFileHDwithinTag(summary9, sumCol9, overallSum9, output_file,
                                  "Hamming distance of each half in the tag: file1", sep)
            createFileHD(summary11, sumCol11, overallSum11, output_file,
                         "Absolute delta Hamming distances within the tag: file1", sep)
            createFileHD(summary13, sumCol13, overallSum13, output_file,
                         "Relative delta Hamming distances within the tag: file1", sep)

            createFileFSD2(summary19, sumCol19, overallSum19, output_file,
                           "Family size distribution with separation after absolute delta Hamming distances: file1",
                           sep)
            createFileFSD2(summary21, sumCol21, overallSum21, output_file,
                           "Family size distribution with separation after relative delta Hamming distances: file1",
                           sep, rel=True)

            if len(minHD_tags_zeros) != 0:
                output_file.write(
                    "All tags were filtered: only those tags where at least one half is identical with the half of the min. tag are kept.\nSo the hamming distance of the non-identical half is compared.\n")
                createFileHD(summary15, sumCol15, overallSum15, output_file,
                             "Hamming distances of non-zero half: file1", sep)
                createFileFSD2(summary23, sumCol23, overallSum23, output_file,
                               "Family size distribution with separation after Hamming distances of non-zero half: file1",
                               sep, diff=False)
            output_file.write("\n")



if __name__ == '__main__':
    sys.exit(Hamming_Distance_Analysis(sys.argv))