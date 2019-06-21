mkdir .tmp-mm
cp $1 .tmp-mm/tmp.tar.bz2
cd .tmp-mm
tar xfvj tmp.tar.bz2
cd metamath

gcc m*.c -o metamath -O3 -funroll-loops -finline-functions -fomit-frame-pointer -Wall -pedantic -DINLINE=inline

cd ..
cd ..
mv .tmp-mm/metamath $2
rm -Rf .tmp-mm
