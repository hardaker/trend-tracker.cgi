#!/usr/bin/perl

use IO::File;
use IO::Dir;
use strict;
use CGI;
use Data::Dumper;
use DBI;

our %config;
our $dbh;

my $runpath = $ENV{'SCRIPT_FILENAME'};
$runpath =~ s/(.*)\/(.*)/$1/;
if (length($runpath) == 0 || ! -d $runpath) {
    Error("Failed to determine initial startup path");
}

my $configfile = "trend-tracker.config";
my $configfullpath = "$runpath/$configfile";

# determine what we shoud be doing
my $cgi = CGI->new;
my $query_type = $cgi->param('type');

read_config($configfile);
init_db();

if ($query_type eq 'submit') {
    handle_submit();
} elsif ($query_type eq 'report') {
    handle_report();
} elsif ($query_type eq 'dump') {
    handle_dump();
} else {
    Error("Unknown input parameters");
}

#######################################################################
# data handling routines
#

# handle incoming data submissions
sub handle_submit {
    print_headers();
    my $key         = $config{'key'};
    my $parameters  = config_array('parameters');
    my $extras      = config_array('extras');
    my $count       = $config{'startat'} || 0;
    my $legalvalues = $config{'values'};
    my $extravalues = $config{'extravalues'};
    my $keyvalues   = $config{'keyvalues'};

    # create the insert statment and prepare it for use
    my $statement = "insert into data (cgipid, timestamp, remoteaddress, $key, " . 
	join(", ", @$parameters) . ", " .
	join(", ", @$extras) .
	") values(" .
	("?, " x ($#$parameters + $#$extras + 5)) . "?)";

    my $sth = $dbh->prepare($statement);
    my $time = time();

    # loop through all the possibilities collecting data
    while (1) {
	last if ($cgi->param($key . $count) eq '');

	# store the key
	my $keyvalue = $cgi->param($key . $count);
	if ($keyvalue !~ /$keyvalues/i) {
	    Error("Illegal key value passed in");
	}

	my @values = ($$, $time);

	# calculate (maybe) the remote address and push it on
	if ($config{'logaddress'}) {
	    my $addr = $cgi->remote_addr();
	    if (lc($config{'logaddress'}) eq "sha1") {
		eval 'require Digest::SHA1';
		$addr = Digest::SHA1::sha1_base64($addr);
	    }
	    $addr;
	    push @values, $addr;
	} else {
	    push @values, ''; ## XXX: make this entirely optional in the future
	}

	push @values, $keyvalue;

        foreach my $parameter (@$parameters) {
	    my $val = $cgi->param($parameter . $count);
	    if ($val !~ /$legalvalues/i) {
		$val = "";
	    }
	    push @values, $val;
	}

	foreach my $parameter (@$extras) {
	    my $val = $cgi->param($parameter);
	    if ($val !~ /$extravalues/i) {
		$val = "";
	    }
	    push @values, $val;
	}

	print "here: $statement" . join(", ", @values) . "\n";
	$count++;
	$sth->execute(@values);
    }

    if ($config{'logaddress'}) {
	my $addr = $cgi->remote_addr();
	if (lc($config{'logaddress'}) eq "sha1") {
	    eval 'require Digest::SHA1';
	    $addr = Digest::SHA1::sha1_base64($addr);
	}
    }
    
    # XXX: do something with the data...
    print "<pre>\n";
    #print Dumper(\%data);
    print "</pre>\n";
}

sub init_db {
    $dbh = DBI->connect("$config{'database'}");
    if (!$dbh) {
	Erorr("Failed to connect to the database");
    }
}


sub handle_report {
    print_headers();
}

sub handle_dump {
    print_headers("text/xml");
}

#######################################################################
# general routines
#
#### WARNING: Must Match Copy in createdb
#             (to keep this file self-contained, we duplicate it here)
sub read_config {
    my ($file) = @_;
    my $fh = new IO::File;
    if (! -f $file || !$fh->open($file)) {
	Error("failed to open the config file: $file");
    }

    while(<$fh>) {
	next if (/^\s*#/);
	next if (/^\s*$/);
	Error ("Illegal configuration directive: $_") if (! /:/);
	
	my ($key, $value) = /^\s*([^:]+):\s*(.*)/;
	$config{$key} = $value;
    }
}

# splits a config token into separate pieces; Default separation is by comma
sub config_array {
    my ($token, $separator) = @_;

    return []          if (!exists($config{$token}));
    $separator = ","   if (!defined($separator));

    my @results = split(/$separator\s*/, $config{$token});
    return \@results;
}

#######################################################################
# utility routines

# prints the starting http headers
my $have_done_headers = 0;
sub print_headers {
    return if ($have_done_headers);
    $have_done_headers = 1;

    my ($type) = @_;

    $type ||= "text/html";
    #
    # print http headers
    #
    print "Content-Type: $type\n\n";
}

sub Error {
    print STDERR @_,"\n";
    print_headers();
    print "<h1>Internal Error; please contact an administrator</h1>\n";
    exit 0;
}
