#####################################################################
#											Make file for the project											#
#####################################################################
CC = gcc
CXX = g++
CFLAGS = -g -Wall -fexceptions

SRCDIR = src
BUILDDIR = build
INC = -I include -I/usr/include/mysql -I/usr/local/include/mysql++
LIB = -L lib -lpthread -lmysqlclient -lmysqlpp -lGL -lGLU -lglut `pkg-config opencv --libs` `visp-config --libs`
TARGET = bin/runner

SRCEXT = cpp
SOURCES = $(shell find $(SRCDIR) -type f -name *.$(SRCEXT))
OBJECTS = $(patsubst $(SRCDIR)/%,$(BUILDDIR)/%,$(SOURCES:.$(SRCEXT)=.o))

all: $(TARGET)

$(TARGET): $(OBJECTS)
	@echo " Linking..."
	@echo " $(CXX) $^ -o $(TARGET) $(LIB)"; $(CXX) $^ -o $(TARGET) $(LIB)

$(BUILDDIR)/%.o: $(SRCDIR)/%.$(SRCEXT)
	@mkdir -p $(BUILDDIR)
	@echo " $(CXX) $(CFLAGS) $(INC) -c -o $@ $<"; $(CXX) $(CFLAGS) $(INC) $(LIB) -c -o $@ $<

clean:
	@echo " Cleaning...";
	@echo " $(RM) -r $(BUILDDIR) $(TARGET)"; $(RM) -r $(BUILDDIR) $(TARGET)

run:
	./bin/runner

.PHONY: all run clean
